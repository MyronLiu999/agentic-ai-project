# UI 测试数据

所有销售数据均为合成数据。CSV 表示经销商的 sell-out 上传文件；报告收入的权威来源仍是本地 orders 数据库。CSV 中的 units 与数据库 units 可以不同，报告应保留并解释差异。

仓库默认联系人：Acme → SYN Acme contact (`contact@acme.example`)；Brightline → SYN Brightline contact (`contact@brightline.example`)；Cedar → SYN Cedar contact (`contact@cedar.example`)。使用个人邮箱覆盖后，以该次生成的 `expected_results.csv` 和请求页为准。

## 直接查看

- http://127.0.0.1:8000/requests/REQ-SYN-thread-2001 ：标准报告预览、六产品收入图和待审邮件。
- http://127.0.0.1:8000/requests/REQ-SYN-thread-2002 ：季度比较报告、产品收入图、Q2/Q3 比较图和待审邮件。
- http://127.0.0.1:8000/query ：选择 distributor / quarter 查看数据库汇总和产品图。

以上前两个请求的新增内容标记为 `ui-demo-preview`，由脚本生成用于检查展示和按钮。它们不是 agent 运行或实验成绩。原有已发送邮件保留历史收件人；新草稿使用新邮箱。

## 从 Console 完整测试

打开 http://127.0.0.1:8000/console ，逐项输入下表命令。新请求 `REQ-SYN-thread-ui-01` 到 `09` 尚未处理。

| CSV / 请求后缀 | 测试内容 | 文件单位总数 | Console 输入 |
|---|---|---:|---|
| 01_standard_q3.csv / ui-01 | 六产品标准报告、图表、邮件 | 1085 | Process request REQ-SYN-thread-ui-01. |
| 02_comparison_q3.csv / ui-02 | Q3 对 Q2、收入差额和比较图 | 1140 | Process request REQ-SYN-thread-ui-02 and compare Q3 against Q2; save both quarters and a comparison chart. |
| 03_german_semicolon_q3.csv / ui-03 | 分号、德文列名、逗号小数 | 1240 | Process request REQ-SYN-thread-ui-03. |
| 04_monthly_units_q3.csv / ui-04 | 三个月列求和 | 965 | Process request REQ-SYN-thread-ui-04. |
| 05_duplicate_zero_q3.csv / ui-05 | 重复 SKU、零值、引号/逗号 | 825 | Process request REQ-SYN-thread-ui-05. |
| 06_invalid_units_q3.csv / ui-06 | 缺失/非数字单位 | 不可确定 | Process request REQ-SYN-thread-ui-06; explain missing data and do not invent totals. |
| 07_empty_q3.csv / ui-07 | 只有表头 | 0 行，无观测 | Process request REQ-SYN-thread-ui-07; explain that the upload is empty. |
| 08_no_orders_q4.csv / ui-08 | 数据库 Q4 无订单、空图 | 0 | Process request REQ-SYN-thread-ui-08. |
| 09_out_of_scope_q3.csv / ui-09 | 保密范围拒绝 | 300 | Process request REQ-SYN-thread-ui-09. |

批处理：在处理 01/05 前，用新会话输入 `Process requests REQ-SYN-thread-ui-01 and REQ-SYN-thread-ui-05 as a batch.`，检查两份报告和各自正确的收件人。

成功后在请求页核对 Reports、Charts、Pending records；再询问 `What is the status of request REQ-SYN-thread-ui-01?`。异常样例用于观察当前处理能力，不能假定每项一定成功；应检查是否解释/澄清、是否捏造数据，以及失败是否清楚显示。空文件的 0 行不等同于零销售。

`expected_results.csv` 从当前数据库生成，列出了每个新请求的当前/上季度收入、变化额、数据库单位和上传单位，可用于人工核对。

待审记录可点击 Discard（不发送）；Send as the operator 在本地 Threads 留下消息。项目当前没有 SMTP/Gmail 投递，真实邮箱只作为联系人显示。Approvals 页面暂为空，外部回复自动续跑属于 M2，不由这些 CSV 实现。

报告邮件现在包含当前请求的 PNG 图表（同名图表采用最新版本，同时保留关联报告指定的主图）。待审邮件显示图片预览；手动邮件表单的 Download email with charts (.eml) 保留你编辑后的主题/正文并内嵌图片，无需访问 localhost 就能查看图片。下载不发送，也不改变请求状态。Send as the operator 会冻结当时的图表并在 Threads 显示，后来生成的图不会修改已发送内容。历史未带图的邮件不会被补写图片；澄清问题不自动附带报告图表。真实邮箱投递仍需通过邮件软件或后续服务接入。

## 重新加载

在本仓库环境中执行 `python -m scripts.prepare_ui_demo --install`。重复执行不重建已存在请求、不重置状态、不重新生成已处理的预览，也不调用模型或发送消息。手动修改过原始 CSV 后请使用新的请求 ID，脚本不会覆盖已有附件。

个人演示可用 `--contact "SYN-DIST-001=Reviewer <reviewer@example.net>"` 覆盖联系人，三个经销商分别对应 001/002/003；多次传入该选项可同时配置。个人版清单和 ZIP 默认写入被 Git 忽略的 `state/ui-demo/`，不会覆盖仓库的合成默认值。后续重新加载时保留同样的参数；不带覆盖参数运行会恢复合成联系人。已发送消息的历史收件人始终保留。

每次安装会一起生成清单和 `ui-test-data.zip`，包含九个 CSV、清单和本说明。仓库 ZIP 与仓库文件一致；个人版 ZIP 与本地清单一致。

如果执行 `make app`，它会重置所有演示状态；之后需再次运行上述加载命令。`make serve` 直接保留已有状态。Console 使用真实模型时会消耗 API tokens。
