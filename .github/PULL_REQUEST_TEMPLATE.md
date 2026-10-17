## 变更说明

<!-- 一句话说明这次改动解决了什么问题 -->

## 变更类型

- [ ] `feat` 新功能
- [ ] `fix` 缺陷修复
- [ ] `refactor` 重构（无外部行为变化）
- [ ] `perf` 性能优化
- [ ] `docs` 文档
- [ ] `test` 测试
- [ ] `chore` 构建/依赖/杂项

## 影响范围

<!-- 改了哪些模块：views/ · queue_manager.py · downloader.py · skin.py · theme.py · 打包 ... -->

## 自测清单（提交前必勾）

- [ ] `python verify.py` 全绿（当前 54 项，退出码 0）
- [ ] 改动界面时跑过 `python screenshot.py`，12 张截图已核对
- [ ] 颜色一律走 `theme.py` 令牌，未硬编码色值
- [ ] 自定义 `QFrame` 样式用了 `#ObjectName` 限定选择器
- [ ] `views/` 层未直接调用 `subprocess` / yt-dlp
- [ ] 后台线程异常已兜底，不会冒泡导致 UI 崩溃
- [ ] 版本号只改了 `bilidownloader/__init__.py`（单一真源）

## 禁止提交项自查

```bash
git ls-files | grep -Ei "cookies|^bin/|^data/|screenshots|\.exe$|dist/|build/"   # 应为空
```

- [ ] 以上命令无输出（未误提交凭证 / 二进制 / 本地数据）

## 关联

<!-- 例如：Closes #12 -->
