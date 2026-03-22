import sys, asyncio, logging
sys.path.insert(0, 'dealscope')
from bot.handlers import user2
logging.basicConfig(level=logging.INFO)
async def run():
    await user2._publish_support_event('support:messages', {'test':'publish_check'})
asyncio.run(run())
