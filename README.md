# ProgressBarTimeLeft
Hello, this is my first "add-on" (which isn't really by me since I just tweaked/merged Glutanimate's Progress Bar add-on with Carlos Duarte's More Decks Stats and Time Left add-on.). I basically got the progress bar to work on 2.1.49, as well as added statistics for cards left, percentage left, time (s) spent per card based on today's reviews, and time left based on how fast you've done today's reviews.   

I have not tested this on any other version besides 2.1.49-2.1.54, but I just wanted to share it since it took me a while to get this working and I'm very proud of it (and am hugely thankful to Glutanimate and Mr. Duarte).  

Installation: Double click the anki-addon file or install the add-on from https://ankiweb.net/shared/info/1097423555

P.S. This is my first time using GitHub and Anki-Web, so please be kind :(

Update see ankiwebs link for changelog

## Configuration
CHANGE ALL VALUES IN reviewer_progress_bar.py <br>
<br>
If True, write "True", otherwise leave it empty (e.g. "")<br>
<br>
Change the following in reviewer_progress_bar.py<br>
"includeNew": "True",<br>
"includeRev": "True",<br>
"includeLrn": "True",<br>
"includeNewAfterRevs": "True",<br>
"scrollingBarWhenEditing": "True",<br>
"invertTF": "",<br>
"forceForward": "",<br>
"showPercent": "True",<br>
"showNumber": "True"<br>
"showRetention": "True"<br>
"showAgain": "True"<br>
"showYesterday": "True"<br>
"showDebug": "False"<br>
"dockArea": "Qt.TopDockWidgetArea"<br>
"orientationHV": "Qt.Horizontal"
"qtxt": "aliceblue",<br>
"qbg": "rgba(0, 0, 0, 0)",<br>
"qfg": "#3399cc",<br>
"qbr": "5",<br>
"maxWidth": "20",<br>
"orientationHV": "Qt.Horizontal",<br>
"tz": 8 #GMT+ CHANGE THIS TO YOUR GMT+_ (negative number if you're GMT-)<br>
