#!/usr/bin/env python3
"""
MoltBot 命令行入口
"""
import asyncio
import argparse
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from moltbot import MoltBot, create_app
from moltbot.logger import setup_logging

def main():
    parser = argparse.ArgumentParser(description="MoltBot CLI")
    parser.add_argument(
        "--model", "-m",
        help="默认模型名称"
    )
    parser.add_argument(
        "--prompt", "-p",
        help="要执行的提示"
    )
    parser.add_argument(
        "--api", action="store_true",
        help="启动 API 服务器"
    )
    parser.add_argument(
        "--api-port", type=int, default=8000,
        help="API 服务器端口"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="详细输出"
    )
    
    args = parser.parse_args()
    
    # 设置日志
    level = "DEBUG" if args.verbose else "INFO"
    setup_logging(level)
    
    if args.api:
        # 启动 API 服务器
        import uvicorn
        from moltbot.api import app as fastapi_app
        
        print(f"启动 MoltBot API 服务器，端口: {args.api_port}")
        uvicorn.run(
            fastapi_app,
            host="0.0.0.0",
            port=args.api_port,
            reload=False
        )
    elif args.prompt:
        # 执行单个提示
        async def run():
            bot = create_app()
            
            # 注册默认模型
            if args.model:
                await bot.register_model(args.model)
            
            print(f"执行提示: {args.prompt[:50]}...")
            
            try:
                result = await bot.execute(args.prompt, args.model)
                print(f"\n结果:\n{result}")
            finally:
                await bot.stop()
        
        asyncio.run(run())
    else:
        # 交互模式
        print("MoltBot 交互模式 (输入 'quit' 退出)")
        print("Usage: moltbot --prompt '你的提示'")
        print("       moltbot --api --api-port 8000")

if __name__ == "__main__":
    main()
