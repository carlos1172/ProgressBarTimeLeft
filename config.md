## Configuration
If True, write "True", otherwise leave it empty (e.g. "")<br>

###newWeight [number]
The default steps for "New" Anki cards are 1min and 10min meaning that you see New cards actually a minimum of *TWO* times that day. You can now configure how many times new cards will be counted.

<b>Values:</b><br/>
"newWeight" = 1<br/>
Quantify '1' time the "new card" time<br/>
Example: Steps (10 1440)<br/><br/>
"newWeight" = 2 (default)<br/>
Quantify '2' times the "new card" time<br/>
Example: Steps (1 10)<br/><br/>
"newWeight" = n<br/>
Quantify 'n' times the "new card" time<br/>
Example: Steps (1 10 10 20 30...)<br/>

My Defaults:<br>
	"includeNew": "True",<br>
	"includeRev": "True",<br>
	"includeLrn": "True",<br>
	"includeNewAfterRevs": "True",<br>
	"newWeight": "4",<br>
	"revWeight": "1",<br>
	"lrnWeight": "1",<br>
	"forceForward": "",<br>
	"qtxt": "aliceblue",<br>
	"qbg": "rgba(0, 0, 0, 0)",<br>
	"qfg": "#3399cc",<br>
	"qbr": "5",<br>
	"maxWidth": "20",<br>
	"scrollingBarWhenEditing": "True",<br>
	"orientationHV": "Qt.Horizontal",<br>
	"invertTF": "",<br>
	"showPercent": "True",<br>
	"showNumber": "True"<br>
	"tz": 8 #GMT+ CHANGE THIS TO YOUR GMT+_ (negative number if you're GMT-)<br>
	
Change the following in reviewer_progress_bar.py<br>
"dockArea": "Qt.TopDockWidgetArea"<br>
"orientationHV": "Qt.Horizontal"