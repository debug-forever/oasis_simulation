# ========================================
# 微博仿真可视化系统 - 简易启动脚本
# ========================================

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  微博仿真可视化系统 - 启动" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "提示: 请按照以下步骤手动启动服务" -ForegroundColor Yellow
Write-Host ""

Write-Host "步骤1: 启动后端服务" -ForegroundColor Green
Write-Host "  在新终端中执行:" -ForegroundColor White
Write-Host "  cd visualization_system\backend" -ForegroundColor Cyan
Write-Host "  python start.py" -ForegroundColor Cyan
Write-Host ""

Write-Host "步骤2: 启动前端服务" -ForegroundColor Green  
Write-Host "  在另一个新终端中执行:" -ForegroundColor White
Write-Host "  cd visualization_system\frontend" -ForegroundColor Cyan
Write-Host "  npm run dev" -ForegroundColor Cyan
Write-Host ""

Write-Host "服务地址:" -ForegroundColor Yellow
Write-Host "  前端: http://localhost:5173" -ForegroundColor White
Write-Host "  后端API文档: http://localhost:8000/docs" -ForegroundColor White
Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
