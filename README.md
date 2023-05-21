ProgressBarTimeLeft Add-on
==========================

This add-on combines the functionalities of Glutanimate's Progress Bar add-on and Carlos Duarte's More Decks Stats and Time Left add-on. It adds a progress bar to Anki, along with additional statistics such as cards left, percentage left, time spent per card based on today's reviews, and estimated time left based on your review speed.

Installation
------------

To install the ProgressBarTimeLeft add-on, follow these steps:

1.  Double-click the Anki add-on file (anki-addon) included in this repository.
2.  Anki will prompt you to confirm the installation. Click "Yes" to proceed.
3.  Once the add-on is installed, restart Anki to activate it.

Alternatively, you can install the add-on directly from the [AnkiWeb](https://ankiweb.net/shared/info/1097423555) page.

Configuration
-------------

To customize the behavior of the ProgressBarTimeLeft add-on, you need to modify certain values in the `reviewer_progress_bar.py` file. Follow the steps below to make the necessary changes:

1.  Locate the `reviewer_progress_bar.py` file in your Anki add-ons directory.

    -   The default location for Anki add-ons on different operating systems:
        -   Windows: `Documents\Anki\addons`
        -   macOS: `~/Library/Application Support/Anki2/addons`
        -   Linux: `~/.local/share/Anki2/addons`
2.  Open the `reviewer_progress_bar.py` file in a text editor.

3.  Look for the following configuration options and modify their values as needed:

    -   `includeNew`: Set to "True" to include new cards in the progress bar, leave empty ("") otherwise.
    -   `includeRev`: Set to "True" to include review cards in the progress bar, leave empty ("") otherwise.
    -   `includeLrn`: Set to "True" to include learning cards in the progress bar, leave empty ("") otherwise.
    -   `includeNewAfterRevs`: Set to "True" to include new cards after reviews in the progress bar, leave empty ("") otherwise.
    -   `scrollingBarWhenEditing`: Set to "True" to enable a scrolling progress bar when editing cards, leave empty ("") otherwise.
    -   `invertTF`: Leave empty ("") to use the default behavior.
    -   `forceForward`: Leave empty ("") to use the default behavior.
    -   `dockArea`: Set the dock area for the progress bar (e.g., "Qt.TopDockWidgetArea").
    -   `qtxt`: Set the text color of the progress bar (e.g., "aliceblue").
    -   `qbg`: Set the background color of the progress bar (e.g., "rgba(0, 0, 0, 0)").
    -   `qfg`: Set the foreground color of the progress bar (e.g., "#3399cc").
    -   `qbr`: Set the border radius of the progress bar (e.g., "5").
    -   `maxWidth`: Set the maximum width of the progress bar (e.g., "20").
    -   `orientationHV`: Set the orientation of the progress bar (e.g., "Qt.Horizontal").
    -   `tz`: Set the time zone offset based on your GMT (e.g., 8 for GMT+8; use a negative number for GMT-).
4.  Save the changes to the `reviewer_progress_bar.py` file.

5.  Restart Anki for the changes to take effect.

Changelog
---------

For a detailed list of changes and updates to the ProgressBarTimeLeft add-on, please refer to the [AnkiWeb](https://ankiweb.net/shared/info/1097423555) page.

Acknowledgments
---------------

I would like to express my gratitude to Glutanimate and Carlos Duarte for their original add-ons, which served as the foundation for this project. Without their contributions, this add-on would not have been possible.

Feedback and Support
--------------------

If you encounter any issues, have suggestions for improvements, or need assistance with the ProgressBarTimeLeft add-on, please feel free to create an issue on the [GitHub repository](https://github.com/your-username/ProgressBarTimeLeft) or reach out to me through AnkiWeb.

License
-------

This add-on is licensed under the [GNU AGPLv3](https://www.gnu.org/licenses/agpl-3.0.en.html). Please review the license terms before using or modifying this add-on.

Thank you for using the ProgressBarTimeLeft add-on! I hope it enhances your Anki experience. If you find it useful, please consider leaving a rating or review on the AnkiWeb page.
