# Shutterbox

**Author:** Ned Nguyen<br>
**Platform:** Linux (Debian/Ubuntu-based), Android (Version 16)<br>
**Tech Stack:** Python

Automatic LAN-only photo and video backup from an Android phone to a Linux home server, with files organized by media type and year. No cloud, no accounts, no proprietary apps on the server side.

```
[ Phone: DCIM/Camera ]
         |
         | FolderSync over SMB (LAN only, instant + scheduled)
         v
[ Samba share on server: \\server\phone-inbox ]
         |
         | landing folder
         v
[ media-sorter (Python + systemd) ]
         |
         | reads EXIF / mediainfo for capture date,
         | falls back to mtime, dedupes by filename
         v
    +----------+----------+
    |                     |
    v                     v
/photos/{YYYY}/      /videos/{YYYY}/
```

## What this is

A small, opinionated stack for one specific job: getting phone photos and videos onto a server automatically, organized the way you want, with no surprises.

The phone runs FolderSync, a free Android app that mirrors a local folder to an SMB share. The server runs Samba (to receive uploads) and a small Python service (to organize them). Photos go to one drive, videos to another. Files are sorted into year folders based on their EXIF capture date. Filenames are preserved exactly. Duplicates are skipped.

## What this isn't

- **Not a photo viewer.** This pipeline only moves files. Use Nextcloud, Immich, PhotoPrism, or just a file manager to browse them.
- **Not a cross-device sync tool.** Files only flow phone → server. Deleting on the phone never deletes on the server.
- **Not a remote-access solution.** Works only on your home LAN. If you want backup-from-anywhere, pair this with a self-hosted VPN (WireGuard / wg-easy) so the phone can reach the server from cellular.
- **Not a backup of your backup.** The server folders are still on local disks. If the disks die, everything is gone. You should still have an off-site backup strategy.

## Why I built it this way

I tried two other approaches first and they didn't fit:

- **Immich** renames every uploaded file to a UUID and stores the original name in its database. Recovering original filenames required querying Postgres for every file, which got fragile fast. Also has many features I didn't want (face recognition, smart search, transcoding) that ate resources.
- **Syncthing** wanted to be a two-way trust relationship and was finicky about its database state. Multiple ghost-file states, send/receive direction confusion, and a "data loss potential" warning if a folder marker went missing.

FolderSync is dumb in a good way: it copies a folder over SMB on a schedule. No state, no database, no peering. Pair it with a tiny Python script and you get exactly the behavior you want, with code you can fully understand in one sitting.

## Repo layout

```
home-lab-photo-backup/
├── README.md
├── LICENSE
├── .gitignore
├── .env.example                 ← copy to .env and edit
├── docs/
│   ├── 01-prerequisites.md
│   ├── 02-server-setup.md       ← Samba install + share config
│   ├── 03-sorter-setup.md       ← Python script + systemd unit
│   ├── 04-phone-setup.md        ← FolderSync configuration
│   ├── 05-troubleshooting.md
│   └── architecture.md
├── samba/
│   └── phone-inbox.conf         ← appended to /etc/samba/smb.conf
├── sorter/
│   ├── sorter.py
│   ├── requirements.txt
│   └── media-sorter.service     ← systemd unit (template)
└── scripts/
    ├── install.sh               ← one-shot installer (interactive)
    └── uninstall.sh             ← removes everything this repo created
```

## Quick start

For a Linux Mint / Ubuntu server with two extra drives mounted somewhere.

```bash
# 1. Clone
git clone https://github.com/<you>/home-lab-photo-backup.git
cd home-lab-photo-backup

# 2. Configure
cp .env.example .env
nano .env    # set SERVER_USER, LANDING_DIR, PHOTO_DEST, VIDEO_DEST

# 3. Install
sudo ./scripts/install.sh

# 4. Set the SMB password (separate from your Linux login password)
sudo smbpasswd -a $SERVER_USER

# 5. On your phone, install FolderSync from Play Store and follow docs/04-phone-setup.md
```

The install script handles: package installs (samba, python3-venv, mediainfo), creating the landing folder with correct ownership, appending the Samba share config, opening UFW for SMB on the LAN subnet, setting up the Python venv, dropping in the systemd unit, and starting the service.

Full step-by-step in `docs/02-server-setup.md` if you'd rather do it manually.

## Configuration

Everything lives in `.env`:

```bash
# User the sorter runs as (must own LANDING_DIR and destinations)
SERVER_USER=youruser

# Where FolderSync uploads land (small, ephemeral, on fast disk if possible)
LANDING_DIR=/mnt/Drive02/phone-inbox

# Where sorted photos go (year subfolders auto-created)
PHOTO_DEST=/mnt/Drive02/Pictures/Camera Roll

# Where sorted videos go (year subfolders auto-created)
VIDEO_DEST=/mnt/Drive03/Videos/Camera Roll

# LAN subnet allowed to reach the SMB share
LAN_SUBNET=192.168.1.0/24

# Sorter timing
QUIESCE_SECONDS=60     # min file age before processing (smaller = faster, larger = safer)
POLL_INTERVAL=30       # seconds between scan passes
```

## How it behaves

| Scenario | What happens |
|---|---|
| You take a new photo | FolderSync's instant-sync notices, uploads to the landing folder. Sorter picks it up within ~60 seconds and moves it to `PHOTO_DEST/{year}/`. |
| You take a video | Same flow, lands in `VIDEO_DEST/{year}/`. |
| Photo has no EXIF date | Sorter falls back to file modification time. |
| Filename already exists in target year folder | Incoming copy is deleted. The existing file is untouched. |
| Same filename in a different year folder | Treated as a new file, not a dup. |
| Two files with same name but different content | The newer arrival is treated as a duplicate and deleted. (Shouldn't happen with Samsung's timestamped filenames.) |
| You delete a photo on the phone | Server keeps its copy. One-way, by design. |
| Server is rebooted | Sorter and Samba both auto-start. FolderSync retries on its next interval. No data lost. |
| Phone is offline | FolderSync queues uploads for the next time it's on Wi-Fi. |

## Filtering out junk

Samsung (and probably other Android OEMs) creates temporary files in `DCIM/Camera` during recording — things like `.temp-*BACK.mp4`, `.temp-*BACK_SEAMLESS.mp4`, and incomplete recordings starting with `.`. Configure FolderSync to skip them with a single filter:

- Type: **Exclude**
- Condition: **File name starts with**
- Value: `.`

The sorter also skips dotfiles and `.tmp` files as a second layer of defense.

## Operational commands

```bash
# Status
sudo systemctl status media-sorter
sudo systemctl status smbd

# Live activity
tail -f ~/scripts/media-sorter/sorter.log

# Inbox depth (should usually be 0, sometimes a few during transitions)
ls /mnt/Drive02/phone-inbox/ | wc -l

# Newest arrivals
ls -lht /mnt/Drive02/Pictures/Camera\ Roll/$(date +%Y)/ | head -5

# Pause sorting (files queue up, nothing lost)
sudo systemctl stop media-sorter

# Resume
sudo systemctl start media-sorter
```

## Troubleshooting at a glance

| Symptom | Most likely cause |
|---|---|
| Phone can't connect to share | UFW blocking, SMB password not set, or SMB v1 selected on phone (must be v2/v3). |
| Auth fails on phone but `smbclient` works on server | Phone keyboard autocorrected the password. Set a simple test password, verify, then rotate. |
| Files upload but never move | Sorter not running, or destination folder permissions wrong. Check `systemctl status media-sorter` and `sorter.log`. |
| Background sync stops working after a few hours | Android battery optimization killed FolderSync's observer. Set FolderSync to **Unrestricted** in battery settings. |
| Files land in wrong year | EXIF/video metadata missing or wrong; sorter fell back to file mtime. No fix at the sorter level — comes down to source files. |
| `.temp-*` or `.NNNNN.mp4` junk uploaded | Add the dotfile filter to FolderSync (above). |

Full troubleshooting in `docs/05-troubleshooting.md`.

## Security notes

- The SMB share is **only** open to the LAN subnet via UFW. Do not forward port 445 from your router to the internet.
- The SMB password is separate from the Linux user password. Use a different one. Store it in a password manager.
- The `force user` and `force group` directives in the Samba share mean every file written by FolderSync is owned by `SERVER_USER`, regardless of how SMB negotiated. This keeps permissions clean for the sorter.
- If you want remote backup (off-LAN), put a VPN in front of it (WireGuard / wg-easy on a separate machine). Don't expose SMB.

## Contributing

Issues and PRs welcome. If you adapted this for a different server OS, different drive layout, or different camera-app filter set, a PR with your changes (or even just a note in `docs/`) helps the next person.

## Lessons from building this

A `LESSONS.md` lives in the repo root with notes on the dead ends — what didn't work and why. Worth reading before assuming a different approach (Immich, Syncthing, Nextcloud's auto-upload) would be simpler. They might be, but I tried them and these are the issues I hit.

## License

MIT. See `LICENSE`.

## Credits

- [FolderSync](https://www.tacit.dk/foldersync/) by Tacit Dynamics — the Android app doing the heavy lifting on the phone side.
- [Samba](https://www.samba.org/) — the SMB server.
- [Pillow](https://python-pillow.org/) — EXIF parsing.
- [pymediainfo](https://github.com/sbraz/pymediainfo) — video metadata parsing.
