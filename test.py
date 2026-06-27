import asyncio

from os import path

from ffmpeg.asyncio import FFmpeg


TEST_FILE = path.join('static', 'knicks_bar.mov')
OUT_FILE = path.join('test', 'knicks_bar.mp4')


async def main():
    t = (
        FFmpeg()
        .input(TEST_FILE)
        .output(OUT_FILE)
    )
    await t.execute()


if __name__ == "__main__":
    asyncio.run(main())





