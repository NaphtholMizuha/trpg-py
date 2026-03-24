## 新增需求

## 修改需求

### 需求:选择类原子操作必须支持单体与范围目标查找
系统必须提供选择类原子操作，用于直接确定单体目标或依据范围、阵营和过滤条件查找目标集合。选择结果必须以统一结构返回，至少包含 `target_ids` 数组。若选择步骤声明了目标选取距离校验，系统必须在产出目标集合前先完成该校验。

#### 场景:范围查找返回多个有效目标
- **当** 调用方执行一次球形范围选择，中心点与半径覆盖三个敌对生物
- **当** 选择条件排除施法者本人
- **那么** 该操作输出包含这三个目标标识的 `target_ids`
- **那么** 输出结果中不包含施法者标识

#### 场景:单体目标超距时选择失败
- **当** 调用方执行一次 `select.target`
- **当** 该步骤声明 `targeting.max_range=5`
- **当** source 与 target 的实际距离大于 5
- **那么** 该步骤执行失败
- **那么** 该步骤不得返回伪造的 `target_ids`

### 需求:选择类原子操作必须支持 `field_map`
系统必须允许选择类原子操作通过 `field_map` 显式声明候选对象的逻辑字段映射，包括但不限于 `id`、`side`、`alive`、`tags`、`position.x` 和 `position.y`。系统不得强制候选对象必须使用固定字段名。若 `select.target` 声明了距离校验，系统必须能够通过 `field_map` 读取目标位置。

#### 场景:范围选择通过 field_map 读取自定义坐标字段
- **当** 候选对象的横纵坐标分别存放在 `space.grid.col` 和 `space.grid.row`
- **当** 选择步骤通过 `field_map` 声明 `position.x -> space.grid.col` 与 `position.y -> space.grid.row`
- **那么** 系统按映射后的字段读取坐标
- **那么** 该步骤仍可正确完成范围筛选

#### 场景:单体目标通过 field_map 读取自定义坐标字段
- **当** `select.target` 需要校验目标距离
- **当** 目标坐标位于自定义字段且步骤提供了 `field_map`
- **那么** 系统按映射后的字段读取目标位置
- **那么** 系统据此完成 source 到 target 的测距

## ADDED Requirements

### 需求:选择类原子操作必须支持显式 targeting 距离校验
系统必须允许 `select.target` 与 `select.area` 在 `args` 中通过 `targeting` 对象显式声明距离校验输入。`targeting` 至少必须支持 `source_position`、`max_range` 和 `range_metric`，系统不得要求调用方把测距规则隐式编码在其他业务字段中。

#### 场景:范围选点显式声明 targeting
- **当** 调用方执行一个 `select.area` 步骤
- **当** 该步骤提供 `targeting.source_position`、`targeting.max_range` 和 `targeting.range_metric`
- **那么** 系统将其识别为需要先执行目标选取距离校验
- **那么** 后续范围解析以该校验结果为前提

### 需求:单体目标选择必须按 source 到 target 的距离校验
系统必须在 `select.target` 声明了 `targeting` 时，使用 `targeting.source_position` 与目标位置进行测距。目标位置必须来自被选目标及其 `field_map` 映射，而不是来自范围原点或其他间接字段。

#### 场景:近战攻击目标在合法距离内
- **当** 调用方执行一次 `select.target`
- **当** source 与 target 的实际距离小于或等于 `targeting.max_range`
- **那么** 该步骤执行成功
- **那么** 输出的 `target_ids` 包含该目标标识

### 需求:范围目标选择必须按 source 到 origin 的距离校验
系统必须在 `select.area` 声明了 `targeting` 时，使用 `targeting.source_position` 与该步骤的 `origin` 进行测距。系统不得用范围内候选对象的位置替代 `origin` 参与这一步校验。

#### 场景:火球术选点超距时选择失败
- **当** 调用方执行一次 `select.area`
- **当** source 与 `origin` 的实际距离大于 `targeting.max_range`
- **那么** 该步骤执行失败
- **那么** 该步骤不得继续进行范围内目标收集

### 需求:目标选取校验必须区分超距失败与合法空结果
系统必须将“超距”与“合法但未命中任何目标”区分开。若目标或选点超距，步骤必须失败；若选点合法但过滤与范围覆盖后没有任何目标，步骤必须成功并返回空 `target_ids`。

#### 场景:合法选点但范围内没有目标
- **当** 调用方执行一次 `select.area`
- **当** source 到 `origin` 的距离在合法范围内
- **当** 范围覆盖与过滤后没有任何候选对象符合条件
- **那么** 该步骤执行成功
- **那么** 该步骤输出 `target_ids=[]`

## 移除需求
