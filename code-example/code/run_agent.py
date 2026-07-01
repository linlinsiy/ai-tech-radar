"""
本地调试脚本 - 独立运行 Agent 服务

无需启动 FastAPI 服务，直接在命令行测试 Agent 功能。

使用方式:
    uv run python run_agent.py                           # 交互模式
    uv run python run_agent.py -q "今天的新闻"            # 单次提问
    uv run python run_agent.py -q "介绍人工智能" -s       # 流式输出
"""
import asyncio
import argparse
import sys

# 在所有导入前加载环境变量，确保后续集成的 SDK 能正确读取配置
import os
from dotenv import load_dotenv
# 读取环境标识，默认为 uat
env = os.getenv('ENV', 'uat').lower()
env_file = f'.env.{env}'
load_dotenv(env_file)

# 云桌面需要禁用代理
os.environ['no_proxy'] = '*'

from app.services.agent_service import AgentService, AgentServiceError
from app.utils.logger import setup_logger, get_logger

# 初始化日志
setup_logger()
logger = get_logger(__name__)


async def run_chat(question: str, stream: bool = False):
    """执行一次对话
    
    Args:
        question: 用户问题
        stream: 是否使用流式输出
    """
    service = AgentService()
    
    if stream:
        print("\n回答: ", end="", flush=True)
        async for chunk in service.chat_stream(question):
            if chunk.get("delta"):
                print(chunk["delta"], end="", flush=True)
            if chunk.get("done"):
                used_search = chunk.get("used_search", False)
        print(f"\n\n[使用搜索: {used_search}]")
    else:
        result = await service.chat(question)
        print(f"\n回答: {result['answer']}")
        print(f"\n[使用搜索: {result['used_search']}]")
        if result.get('search_results'):
            print(f"[搜索结果数: {len(result['search_results'])}]")


async def interactive_mode():
    """交互模式 - 持续对话"""
    print("=" * 50)
    print("TalentsView Agent 本地调试")
    print("输入问题进行对话，输入 quit 退出")
    print("=" * 50)
    
    while True:
        try:
            question = input("\n请输入问题: ").strip()
            if question.lower() in ('quit', 'exit', 'q'):
                break
            if not question:
                continue
            await run_chat(question)
        except AgentServiceError as e:
            print(f"\n错误: {e.message} ({e.error_code})")
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"\n未预期错误: {str(e)}")
            logger.error(f"调试脚本错误: {str(e)}", exc_info=True)
    
    print("\n再见!")


def main():
    parser = argparse.ArgumentParser(
        description="TalentsView Agent 本地调试脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python run_agent.py                        # 进入交互模式
  python run_agent.py -q "今天有什么新闻"     # 单次提问
  python run_agent.py -q "介绍AI" -s         # 流式输出
        """
    )
    parser.add_argument(
        "--question", "-q",
        help="直接提问（不进入交互模式）"
    )
    parser.add_argument(
        "--stream", "-s",
        action="store_true",
        help="使用流式输出"
    )
    
    args = parser.parse_args()
    
    try:
        if args.question:
            asyncio.run(run_chat(args.question, args.stream))
        else:
            asyncio.run(interactive_mode())
    except AgentServiceError as e:
        print(f"错误: {e.message} ({e.error_code})")
        sys.exit(1)
    except Exception as e:
        print(f"启动失败: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
