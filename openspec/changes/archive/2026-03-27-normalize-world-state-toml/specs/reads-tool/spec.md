# reads-tool 规范变更

## 修改需求
### 需求:reads smoke 脚本必须支持正常嵌套 TOML 作为默认状态来源
系统必须让 `smoke/test_reads.py` 读取正常嵌套 TOML world state fixture 作为默认状态来源，禁止继续假设默认 fixture 顶层键本身就是点路径字符串。

#### 场景:开发者运行 reads smoke 脚本
- **当** 开发者执行 `smoke/test_reads.py` 且默认状态文件为 `config/world_state.toml`
- **那么** 脚本可以直接消费嵌套 TOML 解析结果作为 state
- **那么** `reads` 工具仍然使用既有点路径输入读取对应值
