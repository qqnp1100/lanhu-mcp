@echo off
REM 蓝湖 MCP Docker 快速部署脚本 (Windows)
REM 使用方法: setup-env.bat

echo.
echo ========================================
echo 🚀 蓝湖 MCP Server - Docker 部署助手
echo ========================================
echo.

REM 检查 Docker
echo 📦 检查 Docker 环境...
docker --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 未安装 Docker，请先安装 Docker Desktop
    echo    官方文档: https://docs.docker.com/desktop/windows/install/
    pause
    exit /b 1
)

docker-compose --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 未安装 Docker Compose，请先安装
    echo    官方文档: https://docs.docker.com/compose/install/
    pause
    exit /b 1
)

echo ✅ Docker 环境检查通过
echo.

REM 创建 .env 文件
echo 📝 创建配置文件...

(
echo # 蓝湖 MCP 服务器配置
echo # ⚠️ 注意：此文件包含敏感信息，不要提交到 git！
echo.
echo # ==============================================
echo # 必需配置
echo # ==============================================
echo.
echo # 蓝湖 Cookie（必需）
echo LANHU_COOKIE="_ga=GA1.1.1604863826.1745571085; _ga_80BGNFFJQN=GS2.1.s1750057473$o3$g0$t1750057475$j58$l0$h0; tfstk=gb0tHRMZ3pvi4p8BeNxHiQ9GIEAHKHca9Al5o-2GcvHKLxEmn5xZGjwK3Rqg5R2jHJw4ClxZjmHKQvrijqhVkSGj3CyD_HcZ_rzXELDvrflwxzKZep4XGXa0MPPShhlZ_r5eGlXZ6f8vI-dbhrMbRkNz6r__1xZQAJP4GONf5BhQLJNbGGwfR9N4N16jhrOKOJPbl-MbfBhQLSabhbspHJ1_nZndMn1qfw2NlZgL6ktn1J_UG2FTf8GsWZ_fN5ETFfwpBrMQVkG4Dq5Vkohs4xPSCO9Y32hI50MWKG2s2ShoDfT1RP0Z10ZjPKSjsP2TRViRGZGLWJHrlvW9p8gZO4zQxUO-O2ki_2hcGENnEJGZ5rLWaPU_CyFEop7_HDijSlzVCKeqJXgsDg-sr4LCXT28iGOp9iS4fWorA1D0YnCS0Wek6EIV0kRU98Ap9isfhBPLECdA0ireT; user_token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE4MDQyMjc3ODEsImlkIjoiZDBhYjkzMDctZGU2NC00YmRmLTgxNDktOWM1ZjRlYmIzYTM1In0.jiovg6zYbmYlSbWvrPqUXfYR8Qwd3f-lYeZlar-v2zw; session=.eJyMkE2KG0EMRu9SazdI1Sr9-DKNVFLNmCSO6fGQRcjdgxmyz_JbPHjf-92OddbHe7s-z8-6tOOW7dqClAmhD840cogoIk1LqXCGRSYm1XfCXUfWMK5yAZYgcCXUQT0G4-SsANepsDqMQZlZnd16t4EWUbmgR6woELJkfTHI7dKOR50__F735z-17z_fbvdjvtf8tiV42A6yZTFtFLk2RbLN5lhUEbvvo12bGMcKxn04jcqJNRWnisIOXsbHcaBIZ0MRG-M1QUQF1_C-64SZVrhEdSoKofV2aY9feazb_a3Ox3l76TWkAnEAhViTu3ZJLC0bUAai2i7tefqsr7h9eK2UsQGBb6SLt7CAzbgnYpAbebu0z486v4D_OvvnbwAAAP__lJqAzA.aa4rww.8IDO-XlpuLEok6Z9QuROS6myzVo"
echo.
echo # ==============================================
echo # 服务器配置（可选）
echo # ==============================================
echo.
echo # 服务器主机地址
echo SERVER_HOST="127.0.0.1"
echo.
echo # 服务器端口
echo SERVER_PORT=8000
echo.
echo # ==============================================
echo # 飞书机器人配置（可选）
echo # ==============================================
echo.
echo # 飞书 Webhook URL（可选 - 如不需要飞书通知请留空）
echo FEISHU_WEBHOOK_URL=""
echo.
echo # ==============================================
echo # 数据存储配置（可选）
echo # ==============================================
echo.
echo # 数据存储目录
echo DATA_DIR="./data"
echo.
echo # ==============================================
echo # 性能配置（可选）
echo # ==============================================
echo.
echo # HTTP 请求超时时间（秒）
echo HTTP_TIMEOUT=30
echo.
echo # 浏览器视口宽度
echo VIEWPORT_WIDTH=1920
echo.
echo # 浏览器视口高度
echo VIEWPORT_HEIGHT=1080
echo.
echo # ==============================================
echo # 开发配置（可选）
echo # ==============================================
echo.
echo # 调试模式
echo DEBUG="false"
) > .env

echo ✅ 配置文件创建成功: .env
echo.

REM 创建数据目录
echo 📁 创建数据目录...
if not exist "data" mkdir data
if not exist "logs" mkdir logs
echo ✅ 目录创建成功
echo.

REM 构建和启动
echo 🏗️  构建 Docker 镜像...
echo ⏳ 这可能需要几分钟时间，请耐心等待...
docker-compose build

echo.
echo 🚀 启动服务...
docker-compose up -d

echo.
echo ⏱️  等待服务启动（10秒）...
timeout /t 10 /nobreak >nul

REM 检查服务状态
echo.
echo 🔍 检查服务状态...
docker-compose ps | findstr "Up" >nul
if not errorlevel 1 (
    echo ✅ 服务启动成功！
    echo.
    echo 📊 服务信息:
    docker-compose ps
    echo.
    echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    echo 🎉 部署完成！
    echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    echo.
    echo 📝 服务访问地址:
    echo    http://localhost:8000/mcp?role=开发^&name=你的名字
    echo.
    echo 🔧 常用命令:
    echo    查看日志: docker-compose logs -f lanhu-mcp
    echo    停止服务: docker-compose stop
    echo    重启服务: docker-compose restart
    echo    删除服务: docker-compose down
    echo.
    echo 📚 配置 AI 客户端:
    echo    请参考 DEPLOY.md 文档中的「连接 AI 客户端」章节
    echo.
    echo 💡 提示:
    echo    - 配置文件位置: %CD%\.env
    echo    - 数据存储位置: %CD%\data
    echo    - 日志存储位置: %CD%\logs
    echo.
) else (
    echo ❌ 服务启动失败
    echo.
    echo 📋 查看错误日志:
    docker-compose logs --tail=50 lanhu-mcp
    echo.
    echo 💡 常见问题排查:
    echo    1. Cookie 是否正确？
    echo    2. 端口 8000 是否被占用？
    echo    3. Docker Desktop 是否正在运行？
    echo    4. Docker 资源是否充足？
    echo.
    echo 📚 详细文档: 请查看 DEPLOY.md
    pause
    exit /b 1
)

pause

