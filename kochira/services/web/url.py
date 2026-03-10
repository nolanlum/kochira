"""
URL scanner.

Fetches and displays metadata for web pages, images and more.
"""

import humanize
import httpx
import re
import tempfile
from datetime import timedelta
from bs4 import BeautifulSoup
from pymediainfo import MediaInfo
from PIL import Image

from kochira import config
from kochira.service import Service, Config

service = Service(__name__, __doc__)


@service.config
class Config(Config):
    max_size = config.Field(doc="Maximum request size.", default=5 * 1024 * 1024)


HEADERS = {
    'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:102.0) Gecko/20100101 Firefox/102.0'
}

def handle_html(content):
    soup = BeautifulSoup(content)

    title = None

    if soup.title is not None:
        title = re.sub(r"\s+", " ", soup.title.string.strip())

    if not title:
        title = "(no title)"

    return "\x02Web Page Title:\x02 {title}".format(
        title=title
    )


def get_num_image_frames(im):
    try:
        while True:
             im.seek(im.tell() + 1)
    except EOFError:
        pass

    return im.tell()


def handle_image(content):
    with tempfile.NamedTemporaryFile() as f:
        f.write(content)
        im = Image.open(f.name)

    nframes = get_num_image_frames(im)

    info = "\x02Image Info:\x02 {w} x {h}; {size}".format(
        size=humanize.naturalsize(len(content)),
        w=im.size[0],
        h=im.size[1]
    )

    if nframes > 1:
        info += "; animated {t}, {n} frames".format(
            n=nframes,
            t=timedelta(seconds=nframes * im.info["duration"] // 1000)
        )

    return info


def handle_media(content):
    with tempfile.NamedTemporaryFile() as f:
        f.write(content)
        media = MediaInfo.parse(f.name)

    duration = timedelta(seconds=media.tracks[0].duration // 1000)
    num_tracks = len(media.tracks) - 1
    first_video_track = next((track for track in media.tracks if track.track_type == 'Video'), None)
    first_audio_track = next((track for track in media.tracks if track.track_type == 'Audio'), None)

    info = "\x02Media Info:\x02 {n} track{s}, {duration}, {size}".format(
        size=humanize.naturalsize(media.tracks[0].file_size),
        n=num_tracks,
        s='s' if num_tracks != 1 else '',
        duration=duration
    )

    if first_video_track:
        info += "; {w} x {h} {codec}, {bitrate}bps, {framerate}fps".format(
            codec=first_video_track.format,
            bitrate=humanize.naturalsize(first_video_track.bit_rate, gnu=True).lower(),
            framerate=first_video_track.frame_rate,
            w=first_video_track.width,
            h=first_video_track.height
        )
    if first_audio_track:
        info += "; {ch}ch {codec}, {sr}kHz".format(
            codec=first_audio_track.format,
            ch=first_audio_track.channel_s,
            sr=first_audio_track.sampling_rate // 100 / 10
        )

    return info

HANDLERS = {
    "text/html": handle_html,
    "application/xhtml+xml": handle_html,
    "image/jpeg": handle_image,
    "image/png": handle_image,
    "image/gif": handle_image,
    "image/webp": handle_image,

    "audio/ogg": handle_media,
    "video/mkv": handle_media,
    "video/mp4": handle_media,
    "video/webm": handle_media,
}

# url.py uses a local client with verify=False to handle arbitrary user-pasted
# URLs that may have self-signed or otherwise invalid TLS certificates.
@service.hook("channel_message")
async def detect_urls(ctx, origin, target, message):
    found_info = {}

    urls = re.findall(r'http[s]?://[^\s<>"]+|www\.[^\s<>"]+', message)

    async with httpx.AsyncClient(verify=False) as client:
        for i, url in enumerate(urls):
            if not (url.startswith("http:") or url.startswith("https:")):
                url = "http://" + url

            if url not in found_info:
                try:
                    resp = await client.head(url, headers=HEADERS)
                except httpx.RequestError as e:
                    info = "\x02Error:\x02 " + str(e)
                else:
                    content_type = resp.headers.get("content-type", "text/html").split(";")[0]

                    if content_type in HANDLERS:
                        content = b""
                        too_large = False
                        async with client.stream("GET", url, headers=HEADERS) as resp:
                            async for chunk in resp.aiter_bytes(2048):
                                content += chunk
                                if len(content) > ctx.config.max_size:
                                    too_large = True
                                    break

                        if too_large:
                            info = "\x02Content Type:\x02 " + content_type
                        else:
                            info = HANDLERS[content_type](content)
                    else:
                        info = "\x02Content Type:\x02 " + content_type
                found_info[url] = info
            else:
                info = found_info[url]

            if len(urls) == 1:
                await ctx.message(info)
            else:
                await ctx.message("{info} ({i} of {num})".format(
                    i=i + 1,
                    num=len(urls),
                    info=info
                ))
