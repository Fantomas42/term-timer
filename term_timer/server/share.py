"""QR codes of the pages shared from one screen to the phones around."""
import ipaddress
from dataclasses import dataclass
from urllib.parse import urlsplit

import segno

# Modules of light margin around the code, as the standard asks.
QUIET_ZONE = 4


@dataclass(frozen=True)
class ShareCode:
    """
    A QR code of an address, drawn as one SVG path.

    The path fills the dark modules on a grid of one unit per module;
    the page colours it, so the code follows the theme like any text.
    """

    url: str
    size: int
    path: str

    @classmethod
    def encode(cls, url: str) -> 'ShareCode':
        """
        Encode an address, runs of dark modules merged row by row.

        Returns:
            The code, its width in modules and its SVG path.

        """
        code = segno.make(url, error='m', micro=False)
        matrix = code.matrix

        runs: list[str] = []
        for y, row in enumerate(matrix):
            x = 0
            width = len(row)
            while x < width:
                if not row[x]:
                    x += 1
                    continue
                start = x
                while x < width and row[x]:
                    x += 1
                length = x - start
                runs.append(f'M{ start } { y }h{ length }v1h-{ length }z')

        return cls(url=url, size=len(matrix), path=''.join(runs))

    @property
    def view_box(self) -> str:
        """
        The SVG view box, the quiet zone around the modules.

        Returns:
            The four numbers of the viewBox attribute.

        """
        side = self.size + 2 * QUIET_ZONE
        return f'-{ QUIET_ZONE } -{ QUIET_ZONE } { side } { side }'

    @property
    def local(self) -> bool:
        """
        Whether the address only reaches this computer.

        Returns:
            True for localhost and the loopback addresses, which a phone
            scanning the code cannot open.

        """
        host = urlsplit(self.url).hostname or ''
        if host == 'localhost':
            return True
        try:
            return ipaddress.ip_address(host).is_loopback
        except ValueError:
            return False
