# Install

## Requirements

### The gh CLI

oss-inbox is built on the [`gh` CLI](https://cli.github.com),
the official GitHub command-line tool.
The app does not connect to GitHub itself.
In the background, it runs `gh api` for each request to GitHub.
`gh` sends the request with your GitHub login.
The app does not keep a GitHub token of its own.

The app does not work without `gh`.
Install and log in to `gh` before you install oss-inbox.

1. Install `gh` for your system. Follow the
   [installation instructions](https://github.com/cli/cli#installation).
2. Log in with your own GitHub account:

   ```bash
   gh auth login
   ```

3. Make sure that the login works:

   ```bash
   gh auth status
   ```

### Systems

| | Linux | macOS | Windows |
| :-- | :-- | :-- | :-- |
| Status | Tested (Ubuntu, GNOME) | Not tested | Tested (Windows 11) |
| Python | 3.10 or later | 3.10 or later | 3.10 or later |
| `gh` CLI | Yes | Yes | Yes |
| [`uv`](https://docs.astral.sh/uv/getting-started/installation/) | Install from the source | Install from the source | Install from the source |
| Pop-ups | `notify-send` | Built in | Built in |

The executable needs no Python and no `uv`. Only the install from the source needs them.

## Installation

Install oss-inbox in one of the two ways below.

### Download the executable

This way needs no Python.

=== "Linux"

    1. Download `oss-inbox-linux` from the
       [latest release](https://codeberg.org/florence-bockting/oss-inbox/releases/latest).
    2. Make the file executable:

        ```bash
        chmod +x oss-inbox-linux
        ```

    3. Start the app:

        ```bash
        ./oss-inbox-linux web
        ```

=== "macOS"

    1. Download `oss-inbox-macos` from the
       [latest release](https://codeberg.org/florence-bockting/oss-inbox/releases/latest).
    2. Make the file executable:

        ```bash
        chmod +x oss-inbox-macos
        ```

    3. Start the app:

        ```bash
        ./oss-inbox-macos web
        ```

    The file has no signature. macOS shows a warning the first time.
    Right-click the file and select **Open**.

=== "Windows"

    1. Download `oss-inbox-win.exe` from the
       [latest release](https://codeberg.org/florence-bockting/oss-inbox/releases/latest).
    2. Start the app:

        ```powershell
        .\oss-inbox-win.exe web
        ```

    The file has no signature. Windows shows a warning the first time.
    Click **More info**, then **Run anyway**.

The command starts the [daemon](usage.md#basic-commands) and opens http://127.0.0.1:8765 in your browser.
The daemon runs in the background. You can close the terminal.
To stop the daemon, click **Stop daemon** on the web page, or run the file with `stop`,
for example `./oss-inbox-linux stop`.

### Install from the source

Run these commands in a terminal. On Windows, use PowerShell.

1. Get the code:

    ```bash
    git clone https://codeberg.org/florence-bockting/oss-inbox.git
    cd oss-inbox
    ```

2. Install the app with `uv`. This also installs Flask and Textual.

    ```bash
    uv tool install .
    ```

3. Start the app:

    ```bash
    oss-inbox web
    ```

`uv` installs the app in its own environment. It puts the `oss-inbox` command in your `PATH`.
If your shell does not find `oss-inbox`, run `uv tool update-shell`. Then open a new terminal.
The install is a copy of the code. A later change in the folder has no effect on the command.
To use a new release, see [Update an install from the source](#update-an-install-from-the-source).
To change the code, see [Run your changes](developers.md#run-your-changes).

The command starts the [daemon](usage.md#basic-commands) and opens http://127.0.0.1:8765 in your browser.
The daemon runs in the background. You can close the terminal.
To stop the daemon, click **Stop daemon** on the web page, or run `oss-inbox stop`.

Then set up the app in the browser. For the terminal UI, see [Start the app](usage.md#start-the-app).

1. Open the **Repos** tab ([how your inbox is organized](usage.md#how-your-inbox-is-organized)). Click **Load my repos**, or type `owner/repo`.
   Then select the repos to watch.

2. Click **Sync now** and wait for the updates to appear.

## Update to a new release

Each new release appears on the
[releases page](https://codeberg.org/florence-bockting/oss-inbox/releases).
Update the app in the same way that you installed it.

!!! note
    The daemon keeps the old version until you restart it.

!!! warning "Update from gh-inbox"
    Stop the gh-inbox daemon before you start oss-inbox.
    On the first start, oss-inbox moves your data from `~/.local/share/gh-inbox/`
    to `~/.local/share/oss-inbox/`. Your notes file stays where it is.

### Update the executable

=== "Linux"

    1. Stop the daemon: click **Stop daemon** on the web page.
    2. Download the new `oss-inbox-linux` from the
       [latest release](https://codeberg.org/florence-bockting/oss-inbox/releases/latest).
    3. Replace the old file with the new file.
    4. Make the file executable:

        ```bash
        chmod +x oss-inbox-linux
        ```

    5. Start the app again:

        ```bash
        ./oss-inbox-linux web
        ```

=== "macOS"

    1. Stop the daemon: click **Stop daemon** on the web page.
    2. Download the new `oss-inbox-macos` from the
       [latest release](https://codeberg.org/florence-bockting/oss-inbox/releases/latest).
    3. Replace the old file with the new file.
    4. Make the file executable:

        ```bash
        chmod +x oss-inbox-macos
        ```

    5. Start the app again:

        ```bash
        ./oss-inbox-macos web
        ```

=== "Windows"

    1. Stop the daemon: click **Stop daemon** on the web page.
    2. Download the new `oss-inbox-win.exe` from the
       [latest release](https://codeberg.org/florence-bockting/oss-inbox/releases/latest).
    3. Replace the old file with the new file.
    4. Start the app again:

        ```powershell
        .\oss-inbox-win.exe web
        ```

### Update an install from the source

Run these commands in a terminal. On Windows, use PowerShell.

1. Stop the daemon: click **Stop daemon** on the web page.
2. Get the list of releases:

    ```bash
    git fetch --tags
    ```

3. Change to the new release. Replace `v0.1.0` with the release name:

    ```bash
    git checkout v0.1.0
    ```

4. Install again. A new release can add dependencies:

    ```bash
    uv tool install --force .
    ```

5. Start the app again:

    ```bash
    oss-inbox web
    ```

!!! tip "Get the newest code before a release"
    The newest code can contain changes that are not in a release yet.
    To get it, use these commands in place of steps 2 and 3:

    ```bash
    git checkout main
    git pull
    ```
