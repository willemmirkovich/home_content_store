import asyncio

from os import path

from ffmpeg.asyncio import FFmpeg


TEST_FILE = path.join('test', 'lilo_and_stich.mp4')
OUT_FILE = path.join('test', 'lilo_and_stich', 'lilo_and_stich.mpd')


async def main():
    t = (
        FFmpeg()
        .input(TEST_FILE)
        .output(
            OUT_FILE,
            {"codec:v": "libx264", "codec:a": "aac", "profile:v": "high"},
            f="dash",
            seg_duration=3,
            pix_fmt="yuv420p",
        )
    )
    await t.execute()


if __name__ == "__main__":
    asyncio.run(main())





