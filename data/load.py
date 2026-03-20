"""
D&D 5e SRD Markdown 数据导入系统
"""

import os
import re
import uuid
from pathlib import Path
from typing import Optional

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, PointStruct, VectorParams,
    SparseVectorParams, SparseIndexParams, SparseVector,
)

from src.tools import Retriever
from data.chunk_strategies import detect_and_chunk, chunk_by_monster_cards, chunk_by_header_level

# ============================================
# 1. 全局配置
# ============================================

QDRANT_URL = "http://localhost:6333"
COLLECTION_NAME = "dnd_5e_srd_hybrid"
VECTOR_SIZE = 1024

DATA_DIR = Path(__file__).parent / "dnd-5e-srd-markdown"
CONVERTED_DIR = Path(__file__).parent / "converted_markdown"
EXCLUDED_FILES = {"README.md", "CHANGELOG.md", "CONTRIBUTING.md", ""}
BATCH_SIZE = 10


# ============================================
# 2. 表格转文本
# ============================================
def convert_table_to_text(html_table: str) -> str:
    """将 HTML 表格转换为自然语言文本

    处理两种表格类型：
    1. 键值对表格（只有 tbody，每行两列）：转换为 "键: 值" 格式
    2. 多列表格（有 thead）：转换为 "行N: 列1=值1, 列2=值2..." 格式
    """
    # 提取表头
    thead_match = re.search(r'<thead>\s*<tr>(.*?)</tr>\s*</thead>', html_table, re.DOTALL | re.IGNORECASE)
    headers = []
    if thead_match:
        header_cells = re.findall(r'<th[^>]*>(.*?)</th>', thead_match.group(1), re.DOTALL | re.IGNORECASE)
        headers = [re.sub(r'<[^>]+>', '', cell).strip() for cell in header_cells]

    # 提取表体
    tbody_match = re.search(r'<tbody>(.*?)</tbody>', html_table, re.DOTALL | re.IGNORECASE)
    if not tbody_match:
        return ""

    tbody_content = tbody_match.group(1)
    rows = re.findall(r'<tr>(.*?)</tr>', tbody_content, re.DOTALL | re.IGNORECASE)

    result_lines = []

    # 判断表格类型：有表头且多列 -> 多列表格，否则键值对表格
    if headers and len(headers) > 0:
        # 多列表格
        for row in rows:
            cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL | re.IGNORECASE)
            cells = [re.sub(r'<[^>]+>', '', cell).strip() for cell in cells]
            if not cells:
                continue

            # 构建行描述
            row_parts = []
            for i, cell in enumerate(cells):
                if i < len(headers):
                    row_parts.append(f"{headers[i]}={cell}")
                else:
                    row_parts.append(cell)

            result_lines.append(", ".join(row_parts))
    else:
        # 键值对表格
        for row in rows:
            cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL | re.IGNORECASE)
            cells = [re.sub(r'<[^>]+>', '', cell).strip() for cell in cells]
            if len(cells) >= 2:
                result_lines.append(f"{cells[0]}: {cells[1]}")
            elif len(cells) == 1:
                result_lines.append(cells[0])

    return "\n".join(result_lines)


def convert_all_tables_in_content(content: str) -> str:
    """将内容中的所有 HTML 表格转换为自然语言文本"""
    def replace_table(match):
        table_html = match.group(0)
        converted = convert_table_to_text(table_html)
        return converted if converted else table_html

    return re.sub(r'<table[^>]*>.*?</table>', replace_table, content, flags=re.DOTALL | re.IGNORECASE)


# ============================================
# 3. Markdown 分块逻辑
# ============================================
def parse_markdown_by_headers(file_path: Path) -> list[dict]:
    """解析 Markdown 文件，按标题层级分块，建立父子关系

    粒度定义：
    - 父块 = 三级标题（###）范围下的所有内容
    - 子块 = 四级+标题或更细粒度分块

    返回的每个子块包含 parent_id 和 parent_content 字段
    """
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 先转换所有表格
    content = convert_all_tables_in_content(content)

    lines = content.split("\n")
    chunks = []

    # 父块追踪：三级标题（###）为父块边界
    parent_chunks = {}  # {parent_title: {"content": str, "id": str}}
    current_parent_id = None
    current_parent_content = []
    current_parent_title = ""

    header_path, current_content, current_level, current_title = [], [], 0, ""

    def save_chunk():
        """保存当前分块"""
        nonlocal current_content, current_title, current_level
        if not current_content:
            return

        chunk_text = "\n".join(current_content).strip()
        if not chunk_text:
            return

        chunk = {
            "content": chunk_text,
            "metadata": {
                "file": file_path.name,
                "title": current_title,
                "level": current_level,
                "path": header_path.copy(),
            },
        }

        # 建立父子关系：只有四级+标题才是子块
        if current_level >= 4 and current_parent_id:
            chunk["parent_id"] = current_parent_id
            chunk["parent_content"] = "\n".join(current_parent_content).strip()

        chunks.append(chunk)

    for line in lines:
        header_match = re.match(r"^(#{1,6})\s+(.+)$", line)
        if header_match:
            # 先保存之前的分块
            save_chunk()

            level = len(header_match.group(1))
            title = header_match.group(2).strip()

            # 更新标题路径
            if level <= len(header_path):
                header_path = header_path[: level - 1]
            header_path.append(title)

            # 处理父块边界（三级标题 ###）
            if level == 3:
                # 保存之前的父块
                if current_parent_id and current_parent_content:
                    parent_chunks[current_parent_id] = {
                        "content": "\n".join(current_parent_content).strip(),
                        "title": current_parent_title,
                    }

                # 开始新的父块
                current_parent_id = str(uuid.uuid4())
                current_parent_title = title
                current_parent_content = [line]
            elif level < 3:
                # 一级或二级标题，重置父块
                if current_parent_id and current_parent_content:
                    parent_chunks[current_parent_id] = {
                        "content": "\n".join(current_parent_content).strip(),
                        "title": current_parent_title,
                    }
                current_parent_id = None
                current_parent_content = []
                current_parent_title = ""
            elif current_parent_id:
                # 四级+标题，追加到父块内容
                current_parent_content.append(line)

            current_level, current_title, current_content = level, title, [line]
        else:
            current_content.append(line)
            # 非标题行也追加到父块内容
            if current_parent_id:
                current_parent_content.append(line)

    # 保存最后一个分块
    save_chunk()

    # 保存最后一个父块
    if current_parent_id and current_parent_content:
        parent_chunks[current_parent_id] = {
            "content": "\n".join(current_parent_content).strip(),
            "title": current_parent_title,
        }

    return chunks


# ============================================
# 4. Qdrant 数据库操作
# ============================================
def create_collection(client: QdrantClient) -> None:
    collections = client.get_collections().collections
    if COLLECTION_NAME not in [c.name for c in collections]:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config={"dense": VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE)},
            sparse_vectors_config={"sparse": SparseVectorParams(index=SparseIndexParams(on_disk=False))}
        )
        print(f"创建混合检索 collection: {COLLECTION_NAME}")


def upsert_chunks(client: QdrantClient, chunks: list[dict], dense_embeddings: list, sparse_embeddings: list) -> None:
    points = []
    for chunk, dense_v, sparse_v in zip(chunks, dense_embeddings, sparse_embeddings):
        sparse_vector_data = SparseVector(indices=sparse_v.indices.tolist(), values=sparse_v.values.tolist())

        # 构建 payload，包含父子关系
        payload = {**chunk["metadata"], "content": chunk["content"]}

        # 添加父子关系字段（如果存在）
        if "parent_id" in chunk:
            payload["parent_id"] = chunk["parent_id"]
        if "parent_content" in chunk:
            payload["parent_content"] = chunk["parent_content"]

        point = PointStruct(
            id=str(uuid.uuid4()),
            vector={"dense": dense_v, "sparse": sparse_vector_data},
            payload=payload,
        )
        points.append(point)
    if points:
        client.upsert(collection_name=COLLECTION_NAME, points=points)


# ============================================
# 5. 数据入库主流程
# ============================================
def get_content_type(filename: str, relative_path: str = "") -> str:
    """获取内容类型，支持中英文路径"""
    type_map = {
        "spells": "spell", "monsters": "monster", "classes": "class",
        "equipment": "equipment", "magic-items": "magic_item", "feats": "feat",
        "character-creation": "character", "playing-the-game": "rules",
        "animals": "creature", "character-origins": "origin",
        "gameplay-toolbox": "rules", "rules-glossary": "glossary",
    }

    # 中文路径映射
    chinese_type_map = {
        "玩家手册2024": "phb2024",
        "城主指南2024": "dmg2024",
        "怪物图鉴2025": "mm2025",
    }

    # 检查是否在中文路径中
    for cn_name, type_prefix in chinese_type_map.items():
        if cn_name in relative_path or cn_name in filename:
            return type_prefix

    return type_map.get(filename.replace(".md", ""), "general")


def load_all_documents(
    include_srd: bool = True,
    include_converted: bool = True,
    converted_book_filter: Optional[list[str]] = None,
) -> None:
    """加载所有文档到 Qdrant

    Args:
        include_srd: 是否包含原始 SRD Markdown 文件
        include_converted: 是否包含转换后的不全书 Markdown
        converted_book_filter: 可选，指定要加载的书籍列表
    """
    # 使用 Retriever 获取嵌入功能
    retriever = Retriever(qdrant_url=QDRANT_URL, collection_name=COLLECTION_NAME)

    create_collection(retriever.qdrant_client)

    all_md_files: list[tuple[Path, str]] = []  # (file_path, relative_dir)

    # 收集 SRD 文件
    if include_srd and DATA_DIR.exists():
        srd_files = [
            (f, "srd")
            for f in DATA_DIR.glob("*.md")
            if f.name not in EXCLUDED_FILES
        ]
        all_md_files.extend(srd_files)
        print(f"发现 {len(srd_files)} 个 SRD 文件")

    # 收集转换后的文件
    if include_converted and CONVERTED_DIR.exists():
        converted_files = []
        for md_file in CONVERTED_DIR.rglob("*.md"):
            # 获取相对路径用于类型判断
            try:
                rel_path = str(md_file.relative_to(CONVERTED_DIR))
            except ValueError:
                rel_path = md_file.name

            # 检查书籍过滤器
            if converted_book_filter:
                if not any(book in rel_path for book in converted_book_filter):
                    continue

            converted_files.append((md_file, rel_path))

        all_md_files.extend(converted_files)
        print(f"发现 {len(converted_files)} 个转换后的文件")

    if not all_md_files:
        print("没有找到任何 Markdown 文件！")
        return

    total_chunks = 0

    for md_file, rel_dir in all_md_files:
        print(f"入库中: {md_file.name}...")

        # 根据文件类型选择分块策略
        if rel_dir == "srd":
            # SRD 文件使用传统标题分块
            chunks = parse_markdown_by_headers(md_file)
        else:
            # 转换后的不全书使用智能检测分块
            chunks = detect_and_chunk(md_file)

        if not chunks:
            continue

        content_type = get_content_type(md_file.name, rel_dir)
        source_tag = "srd" if rel_dir == "srd" else "不全书"

        for chunk in chunks:
            chunk["metadata"]["type"] = content_type
            chunk["metadata"]["source"] = source_tag

        for i in range(0, len(chunks), BATCH_SIZE):
            batch = chunks[i : i + BATCH_SIZE]
            texts_to_embed = [f"{' > '.join(c['metadata']['path'])}\n{c['content']}" for c in batch]
            dense_vecs = retriever.get_dense_embeddings(texts_to_embed)
            sparse_vecs = retriever.get_sparse_embeddings(texts_to_embed)
            upsert_chunks(retriever.qdrant_client, batch, dense_vecs, sparse_vecs)
            total_chunks += len(batch)

    print(f"\n✅ 入库完成！共索引了 {total_chunks} 个区块。")


if __name__ == "__main__":
    # 如果还没有跑过入库，请取消注释
    # load_all_documents()

    # 测试检索
    retriever = Retriever(qdrant_url=QDRANT_URL, collection_name=COLLECTION_NAME)

    print("\n" + "=" * 60)
    print("测试 1: 中文查询")
    print("=" * 60)
    retriever.search_verbose("野蛮人生命骰", limit=3)

    print("\n" + "=" * 60)
    print("测试 2: 英文查询")
    print("=" * 60)
    retriever.search_verbose("How does barbarian rage work?", limit=3)