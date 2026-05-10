# Manual Prompt Examples

## Simple: Say Hello

```bash
uv run taskweavn run \
    --task "write a hello.py that prints hi, then run it" \
    --workspace ./workspace \
    --max-steps 10
```

## Medium: Sales Summary

```bash
uv run taskweavn run \
  --task "在 workspace 里造一个 sales.csv（month,revenue 三个月，10 行），用 run_code 按 month 聚合 revenue 总和，结果写入 monthly_summary.json，再把 top-1 月份打印出来。" \
  --audit --thoughts
```

## Medium: Prime Function With Tests

```bash
uv run taskweavn run \
  --task "在 primes.py 里实现 is_prime(n)，再写 test_primes.py 至少 5 个测试用例（含边界 0/1/2/负数/大素数），用 run_code 执行 'python -m unittest test_primes -v' 风格的等价代码，把通过/失败逐条列出。" \
  --audit --thoughts --thoughts-phases plan,reason
```

## Medium: Log Parsing

```bash
uv run taskweavn run \
  --task "造一个 logs.txt（20 行 JSON-lines，含 level/message 字段，level 在 INFO/WARN/ERROR 中），用 run_code 解析，统计每个 level 的次数与最近一条 ERROR 的 message，结果写到 report.json。最后用 ReadFileTool 把 report.json 读回来贴在 final_answer 里。" \
  --audit --thoughts --thoughts-db ./logs/run.sqlite
```

## Phase 3.8: Personal Site

```bash
taskweavn run \
  --task "帮我创建一个个人主页项目。需要 index.html、styles.css、README.md。页面包含姓名占位、简介、项目列表、联系方式。完成后可以用 shell 命令列出文件确认。" \
  --workspace ./workspace/user-test-medium \
  --max-steps 15 \
  --autonomy risk_gated \
  --risk-assessor baseline
```
