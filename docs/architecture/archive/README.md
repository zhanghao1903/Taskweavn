# Architecture Original 文档归档

> Status: historical calibration evidence
>
> Relocated: 2026-07-22
>
> Inventory: 24 original snapshots

[`original/`](original/) 保存 architecture 事实校准开始前的 byte-for-byte 文档快照。
这些文件仅用于历史比对和 provenance 核验，不描述当前实现，也不是另一套 active
architecture。

2026-07-22，original 文档从 `docs/architecture/` 顶层迁移到
`docs/architecture/archive/original/`。迁移只改变路径，不修改归档文件内容。

## 使用入口

- 当前架构事实与完整文档目录：[../README.md](../README.md)
- 校准证据与 original provenance manifest：[../fix-log/README.md](../fix-log/README.md)
- 原始文档快照：[original/](original/)

## 目录约定

~~~text
docs/architecture/<name>.md
docs/architecture/archive/original/<name>.original.md
docs/architecture/fix-log/<name>.md
~~~

## 维护规则

1. 不得把 original 当作当前实现事实。
2. 不得随 active 文档更新 original；归档快照必须保持首次校准时的内容。
3. 新文档首次校准前，应先创建 `original/<name>.original.md`，再改写 active 文档。
4. source revision、Git blob 和 SHA-256 统一登记在
   [fix-log/README.md](../fix-log/README.md#11-完整-original-provenance-manifest)。
5. 移动归档文件时必须同步所有链接和核验命令，并验证内容哈希不变。
