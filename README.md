# Gacha Tracker

A self-hosted warp tracker for **Honkai: Star Rail**. It imports your warp history straight from the game, keeps it in your own database and shows your pity, 50/50 results and the pulls each character and light cone cost you. More games are planned.

<!-- TODO: screenshot, e.g. ![Overview](docs/overview.png) -->

> [!NOTE]
> Gacha Tracker is a fan project. It is not affiliated with or endorsed by HoYoverse.

## Features

- **Import from the game:** paste your warp history URL and every banner type is imported, including collaboration warps and pets. Run it again later and only new pulls are added.
- **Banner overview:** current pity, average pulls per 5★, 50/50 win rate and the Stellar Jade you spent on each banner type.
- **Item overview:** every character and light cone you own, filtered by rarity, path and type, with Eidolon and Superimposition levels.
- **Pull costs:** how many pulls each item took, in total and on average. Pulls before a lost 50/50 count toward the next featured 5★.
- **Migration from HSR-Warptracker:** import the database file of the old tool.
- **Languages:** English and German. The language follows your browser.

## Installation

You need Docker with Docker Compose.

1. Create a folder and download [`compose.yaml`](compose.yaml) and [`.env.example`](.env.example) into it.
2. Rename `.env.example` to `.env`. Then add every address you will open the tracker with to `ALLOWED_HOSTS`, for example the server's IP address:

   ```env
   ALLOWED_HOSTS=localhost,127.0.0.1,192.168.1.50
   ```

   If an address is missing, that address answers with `Bad Request (400)`.
3. Start the container:

   ```sh
   docker compose up -d
   ```

4. Open `http://<your-server>:8000` and create your admin account.

> [!IMPORTANT]
> Whoever opens the tracker first creates the admin account. Create your account before you make the tracker reachable from the internet.

The secret key is generated on the first start and stored in the data volume. You don't have to set it yourself.

## Configuration

All settings are environment variables in `.env`. After you change one, run `docker compose up -d` again.

| Variable | Default | Description |
|---|---|---|
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` | Comma-separated host names or IP addresses the tracker answers to. |
| `TIME_ZONE` | `UTC` | Time zone used to display pull times, for example `Europe/Berlin`. |
| `REQUIRE_LOGIN` | `True` | Set to `False` to use the tracker without logging in. Only do this when no one else can reach it. |
| `CSRF_TRUSTED_ORIGINS` | – | Full origin when you run the tracker behind a reverse proxy, for example `https://tracker.example.com`. |
| `SERVE_MEDIA` | `True` | Set to `False` when your reverse proxy serves `/media/` itself. |
| `LOG_LEVEL` | `INFO` | Set to `DEBUG` when you are troubleshooting. |
| `SECRET_KEY` | generated | Only set this to replace the generated key. |
| `DATABASE_URL` | SQLite in the data volume | Optional. Point it to a PostgreSQL database, for example `postgres://user:pass@db:5432/gacha`. |

## Importing your warps

1. Open the warp history in the game. This works on PC.
2. On the **Import** page, copy the PowerShell command and run it. It copies your warp history URL to the clipboard.
3. Paste the URL and start the import.

The URL contains a temporary authkey. Gacha Tracker uses it for this import and doesn't store it. The authkey expires after about a day. To import new pulls later, open the warp history in the game again and get a new URL.

### Migrating from HSR-Warptracker

If you used the older [HSR-Warptracker](https://github.com/Haencky/HSR-Warps), you can import its `db.sqlite3` file on the **Import** page.

## Updating

```sh
docker compose pull
docker compose up -d
```

Database migrations run automatically when the container starts.

## Backup

All data is stored in the Docker volume `data`: the database, the secret key and the downloaded images. To create a backup, run:

```sh
docker compose stop
docker run --rm -v gacha-tracker_data:/data -v "$PWD":/backup alpine tar czf /backup/gacha-tracker-backup.tar.gz -C /data .
docker compose start
```

The volume name starts with the name of the folder that contains `compose.yaml`. Run `docker volume ls` to find the exact name.

> [!WARNING]
> `docker compose down -v` **deletes the volume and all your data.** Use `docker compose down` without `-v`.

## Reverse proxy

If you run the tracker behind a reverse proxy such as nginx, Caddy or Traefik:

- Add your domain to `ALLOWED_HOSTS`.
- Set `CSRF_TRUSTED_ORIGINS` to the full origin, for example `https://tracker.example.com`. Without it, logging in and importing fail with a CSRF error.
- Optionally, let the proxy serve the images from the volume's `media/` folder at `/media/` and set `SERVE_MEDIA=False`.

## Credits

- [fribbels/hsr-optimizer](https://github.com/fribbels/hsr-optimizer) for the character and light cone data and images
- [Prydwen](https://www.prydwen.gg/star-rail/) for the build guides linked on the item pages
- [Star Rail Station](https://starrailstation.com/) for the PowerShell script that reads the warp history URL
- Built with [Django](https://www.djangoproject.com/), [htmx](https://htmx.org/), [Tailwind CSS](https://tailwindcss.com/) and [daisyUI](https://daisyui.com/)

## License

The source code is licensed under MIT. See [LICENSE](LICENSE).

Honkai: Star Rail and all game assets, such as names and images, are trademarks and copyright of HoYoverse. They are not covered by the MIT license.
