# GitHub Inbox

> [!NOTE]
> This app is a prototype in a test phase. Feedback is welcome: please
> [open an issue](https://github.com/florence-bockting/gh-inbox/issues).

A local inbox for your GitHub notifications. It separates the items that need
your action from the items that you only want to follow. It reminds you again
when you do not act.

The app uses the [`gh` CLI](https://cli.github.com/) for each GitHub request. It
uses no AI service and no extra token. It sends only read requests, so it never
changes anything on GitHub. All data stays on your computer.

**Documentation:** https://florence-bockting.github.io/gh-inbox/

Use the app in your browser:

![The web page of GitHub Inbox](docs/icons/web-app.png)

Or use it in your terminal:

![The terminal UI of GitHub Inbox](docs/icons/terminal-app.png)

## Quick start

1. Install the [`gh` CLI](https://cli.github.com). Then log in with `gh auth login`.
2. Download the file for your system from the
   [latest release](https://github.com/florence-bockting/gh-inbox/releases/latest).
3. On Linux and macOS, make the file executable: `chmod +x gh-inbox-linux`.
4. Start the app: `./gh-inbox-linux web`.

To install from the source, see [Install](https://florence-bockting.github.io/gh-inbox/install/).

## License

MIT. See [LICENSE](LICENSE).
