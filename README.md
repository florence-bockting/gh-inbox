# oss-inbox

> [!NOTE]
> This app is a prototype in a test phase. Feedback is welcome: please
> [open an issue](https://codeberg.org/florence-bockting/oss-inbox/issues).

A local inbox for your GitHub and Codeberg notifications. It separates the items that need
your action from the items that you only want to follow. It reminds you again
when you do not act.

The app uses the [`gh` CLI](https://cli.github.com/) for each GitHub request. It sends only read requests, so it never
changes anything on GitHub. All data stays on your computer.

**Documentation:** https://florence-bockting.codeberg.page/oss-inbox/

Use the app in your browser:

![The web page of oss-inbox](docs/icons/web-app.png)

Or use it in your terminal:

![The terminal UI of oss-inbox](docs/icons/terminal-app.png)

## Vision

oss-inbox currently supports GitHub fully and Codeberg in a first version. In the
future, it will also collect the notifications from other platforms, for example
GitLab and other Forgejo servers. The goal is one inbox for all your open-source work.

The app had the name gh-inbox before.

## Quick start

1. Install the [`gh` CLI](https://cli.github.com). Then log in with `gh auth login`.
2. Download the file for your system from the
   [latest release](https://codeberg.org/florence-bockting/oss-inbox/releases/latest).
3. On Linux and macOS, make the file executable: `chmod +x oss-inbox-linux`.
4. Start the app: `./oss-inbox-linux web`.

To install from the source, see [Install](https://florence-bockting.codeberg.page/oss-inbox/install/).

## AI assistance

This app has been created with AI assistance.

## License

MIT. See [LICENSE](LICENSE).

oss-inbox is not affiliated with or endorsed by GitHub.
