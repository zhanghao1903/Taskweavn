# 个人网站 - 张三

一个简洁的个人品牌展示网站，包含首页（Hero）、关于我（About）、项目（Projects）、联系（Contact）四个核心区域。

## 预览方法

### 方式一：使用 VS Code Live Server（推荐）

1. 用 VS Code 打开本目录
2. 安装 [Live Server](https://marketplace.visualstudio.com/items?itemName=ritwickdey.LiveServer) 插件
3. 右键 `index.html` → **Open with Live Server**
4. 浏览器自动打开 `http://127.0.0.1:5500`

### 方式二：使用 Python 内置服务器

```bash
# Python 3
python -m http.server 8000 -d personal-site

# 或 Python 2
python -m SimpleHTTPServer 8000
```

然后访问 `http://localhost:8000`

### 方式三：直接打开（简单但某些功能受限）

双击 `index.html` 用浏览器直接打开即可。

## 项目结构

```
personal-site/
├── index.html      # 主页面
├── style.css       # 独立样式表
├── README.md       # 本文件
└── TODO.md         # 后续优化计划
```

## 技术栈

- HTML5
- CSS3（独立文件，无任何第三方依赖）
- 栅格布局 & Flexbox
- 响应式设计

## 许可

MIT
