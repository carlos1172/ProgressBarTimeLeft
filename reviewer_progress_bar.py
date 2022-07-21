# -*- coding: utf-8 -*-
"""
Anki Add-on: Progress Bar
Shows progress in the Reviewer in terms of passed cards per session.
Copyright:  (c) Unknown author (nest0r/Ja-Dark?) 2017
            (c) SebastienGllmt 2017 <https://github.com/SebastienGllmt/>
            (c) liuzikai 2018-2020 <https://github.com/liuzikai>
            (c) Glutanimate 2017-2018 <https://glutanimate.com/>
License: GNU AGPLv3 or later <https://www.gnu.org/licenses/agpl.html>
"""

# Do not modify the following lines
from __future__ import unicode_literals
from typing import Optional

from anki.hooks import addHook, wrap
from anki import version as anki_version

from aqt.utils import showInfo

from aqt.qt import *
from aqt import mw

import anki
from anki.lang import _, ngettext
import aqt
from aqt.utils import tooltip

import math

from datetime import datetime, timezone, timedelta, date
import time

import anki.stats

#-------------Configuration------------------
config = mw.addonManager.getConfig(__name__)
# The default steps for "New" Anki cards are 1min and 10min meaning that you see New cards actually a minimum of *TWO* times that day
# You can now configure how many times new cards will be counted.
# CountTimesNew = 1 (old version)
# Quantify '1' time the "new card" time | Example: Steps (10 1440)
# CountTimesNew = 2 (default)
# Quantify '2' times the "new card" time | Example: Steps (1 10)
# CountTimesNew = n
# Quantify 'n' times the "new card" time | Example: Steps (1 10 10 20 30...)
#-------------Configuration------------------

############## USER CONFIGURATION START ##############

# CARD TALLY CALCULATION

# Which queues to include in the progress calculation (all True by default)
includeNew =  1
includeRev = 1
includeLrn = 1

# Only include new cards once reviews are exhausted.
includeNewAfterRevs = 1

# Calculation weights
#
#   Setting proper weights will make the progress bar goes smoothly and reasonably.
#
#   For example, if all weight are 1, and you set 2 steps for a new card in your desk config, you will convey
#   one 'new' into two 'learning' card if you press 'again' at the first time, which will increase remaining
#   count and cause the bar to move backward.
#
#   In this case, it's probably a good idea to set newWeight to 2, and remaining count will be calculated as
#   new * 2 + learn + review. Now pressing 'again' will just make it stop going forward, but not backward. If
#   you press 'easy' at first, the progress will go twice as fast, which is still reasonable.
#
#   However, if you press 'good' followed by 'again', there will be another two learning card again, and the
#   progress still needs to go backward. It may not be a big deal, but if you want the progress never goes
#   backward strictly, enable forceForward below.
#
#   Weights should be integers. It's their relative sizes that matters, not absolute values.
#
#   Another example that make the progress goes unstably is 'bury related new cards to next day.' If you have
#   three new cards in a note, there will be 3 new cards at the beginning of your review, but another two will
#   disappear instantly after you learn one of them. However, all three cards will be regarded as 'completed,'
#   so your progress may go three times as fast.

# newWeight = float(config['newWeight'])
# revWeight = float(config['revWeight'])
# lrnWeight = float(config['lrnWeight'])
lrnSteps = 3

# If enabled, the progress will freeze if remaining count has to increase to prevent moving backward,
#   and wait until your correct answers 'make up' this additional part.
#   NOTE: This will not stop the progress from moving backward if you add cards or toggle suspended.
forceForward = 0

# PROGRESS BAR APPEARANCE

showPercent = 1  # DEFAULT: 1 Show the progress text percentage or not.
showRetention = 1  # DEFAULT: 1 Show the retention or not.
showSuperMatureRetention = 1 # DEFAULT: 1 Show Super Mature Retention
showAgain = 1 # DEFAULT: 1 Show again rate or not
showNumber = 1  # DEFAULT: 1 Show the progress text as a fraction
showYesterday = 1 # DEFAULT: 1 Show yesterday's values in parenthesis
showDebug = 0 # DEFAULT: 0 Show New/Lrn/Rev Weights used for computation
useToday = 0 # DEFAULT: 0 WARNING: useToday, useAverage, and useYesterday cannot be used at the same time. CHOOSE ONLY ONE. Uses today's lrn/rev/new weights for ETA.
useAverage = 1 # DEFAULT: 1 WARNING: useToday, useAverage, and useYesterday cannot be used at the same time. CHOOSE ONLY ONE. Uses 2-day average lrn/rev/new weights for ETA.
useYesterday = 0 # DEFAULT: 0 WARNING: useToday, useAverage, and useYesterday cannot be used at the same time. CHOOSE ONLY ONE. Uses yesterday's lrn/rev/new weights for ETA.

qtxt = "aliceblue"  # Percentage color, if text visible.
qbg = "rgba(0, 0, 0, 0)"  # Background color of progress bar.
qfg = "#3399cc"  # Foreground color of progress bar.
qbr = 5  # Border radius (> 0 for rounded corners).

# optionally restricts progress bar width
maxWidth = 20  # (e.g. "5px". default: "")

scrollingBarWhenEditing = 1  # Make the progress bar 'scrolling' when waiting to resume.

orientationHV = Qt.Orientation.Horizontal  # Show bar horizontally (side to side). Use with top/bottom dockArea.
# orientationHV = Qt.Vertical # Show bar vertically (up and down). Use with right/left dockArea.

invertTF = 0  # If set to True, inverts and goes from right to left or top to bottom.

dockArea = Qt.DockWidgetArea.TopDockWidgetArea # Shows bar at the top. Use with horizontal orientation.
# dockArea = Qt.BottomDockWidgetArea # Shows bar at the bottom. Use with horizontal orientation.
# dockArea = Qt.RightDockWidgetArea # Shows bar at right. Use with vertical orientation.
# dockArea = Qt.LeftDockWidgetArea # Shows bar at left. Use with vertical orientation.

pbStyle = ""  # Stylesheet used only if blank. Else uses QPalette + theme style.
'''pbStyle options (insert a quoted word above):
    -- "plastique", "windowsxp", "windows", "windowsvista", "motif", "cde", "cleanlooks"
    -- "macintosh", "gtk", or "fusion" might also work
    -- "windowsvista" unfortunately ignores custom colors, due to animation?
    -- Some styles don't reset bar appearance fully on undo. An annoyance.
    -- Themes gallery: http://doc.qt.io/qt-4.8/gallery.html'''

##############  USER CONFIGURATION END  ##############

# Set up variables

remainCount = {}  # {did: remaining count (weighted) of the deck}
doneCount = {}  # {did: done count (weighted) of the deck}, calculated as total - remain when showing next question
totalCount = {}  # {did: max total count (weighted) that was seen}, calculated as remain + done after state change
# NOTE: did stands for 'deck id'
# For old API of deckDueList(), these counts don't include cards in children decks. For new deck_due_tree(), they do.

currDID: Optional[int] = None  # current deck id (None means at the deck browser)

nmStyleApplied = 0
nmUnavailable = 0
progressBar: Optional[QProgressBar] = None

pbdStyle = QStyleFactory.create("%s" % pbStyle)  # Don't touch.

# Defining palette in case needed for custom colors with themes.
palette = QPalette()
palette.setColor(QPalette.ColorRole.Base, QColor(qbg))
palette.setColor(QPalette.ColorRole.Highlight, QColor(qfg))
palette.setColor(QPalette.ColorRole.Button, QColor(qbg))
palette.setColor(QPalette.ColorRole.WindowText, QColor(qtxt))
palette.setColor(QPalette.ColorRole.Window, QColor(qbg))

if maxWidth:
    if orientationHV == Qt.Orientation.Horizontal:
        restrictSize = "max-height: %s;" % maxWidth
    else:
        restrictSize = "max-width: %s;" % maxWidth
else:
    restrictSize = ""

try:
    # Remove that annoying separator strip if we have Night Mode, avoiding conflicts with this add-on.
    import Night_Mode

    Night_Mode.nm_css_menu \
        += Night_Mode.nm_css_menu \
           + '''
        QMainWindow::separator
    {
        width: 0px;
        height: 0px;
    }
    '''
except ImportError:
    nmUnavailable = 1

def initPB() -> None:
    """Initialize and set parameters for progress bar, adding it to the dock."""
    global progressBar
    progressBar = QProgressBar()
    progressBar.setTextVisible(showPercent or showNumber)
    progressBar.setInvertedAppearance(invertTF)
    progressBar.setOrientation(orientationHV)
    if pbdStyle is None:
        progressBar.setStyleSheet(
            '''
                QProgressBar
                {
                    text-align:center;
                    color:%s;
                    background-color: %s;
                    border-radius: %dpx;
                    %s
                }
                QProgressBar::chunk
                {
                    background-color: %s;
                    margin: 0px;
                    border-radius: %dpx;
                }
                ''' % (qtxt, qbg, qbr, restrictSize, qfg, qbr))
    else:
        progressBar.setStyle(pbdStyle)
        progressBar.setPalette(palette)
    _dock(progressBar)


def _dock(pb: QProgressBar) -> QDockWidget:
    """Dock for the progress bar. Giving it a blank title bar,
        making sure to set focus back to the reviewer."""
    dock = QDockWidget()
    tWidget = QWidget()
    dock.setObjectName("pbDock")
    dock.setWidget(pb)
    dock.setTitleBarWidget(tWidget)
 
    # Note: if there is another widget already in this dock position, we have to add ourself to the list

    # first check existing widgets
    existing_widgets = [widget for widget in mw.findChildren(QDockWidget) if mw.dockWidgetArea(widget) == dockArea]

    # then add ourselves
    mw.addDockWidget(dockArea, dock)

    # stack with any existing widgets
    if len(existing_widgets) > 0:
        mw.setDockNestingEnabled(True)

        if dockArea == Qt.DockWidgetArea.TopDockWidgetArea or dockArea == Qt.BottomDockWidgetArea:
            stack_method = Qt.Vertical
        if dockArea == Qt.LeftDockWidgetArea or dockArea == Qt.RightDockWidgetArea:
            stack_method = Qt.Orientation.Horizontal
        mw.splitDockWidget(existing_widgets[0], dock, stack_method)

    if qbr > 0 or pbdStyle is not None:
        # Matches background for round corners.
        # Also handles background for themes' percentage text.
        mw.setPalette(palette)
    mw.web.setFocus()
    return dock

def updatePB():
    # Get studdied cards  and true retention stats. TODAY'S VALUES
    
    y = (mw.col.sched.day_cutoff-86400)*1000
    
    cards, failed, distinct, flunked, passed, passed_supermature, flunked_supermature, learned, relearned, thetime = mw.col.db.first("""
    select
    sum(case when ease >=1 then 1 else 0 end), /* cards */
    sum(case when ease = 1 then 1 else 0 end), /* failed */
    count(distinct cid), /* distinct */
    sum(case when ease = 1 and type == 1 then 1 else 0 end), /* flunked */
    sum(case when ease > 1 and type == 1 then 1 else 0 end), /* passed */
    sum(case when ease > 1 and type == 1 and lastIvl >= 100 then 1 else 0 end), /* passed_supermature */
    sum(case when ease = 1 and type == 1 and lastIvl >= 100 then 1 else 0 end), /* flunked_supermature */
    sum(case when ivl > 0 and type == 0 then 1 else 0 end), /* learned */
    sum(case when ivl > 0 and type == 2 then 1 else 0 end), /* relearned */
    sum(time)/1000 /* thetime */
    from revlog where id > ? """,y)
    cards = cards or 0
    failed = failed or 0
    distinct = distinct or 0
    flunked = flunked or 0
    passed = passed or 0
    passed_supermature = passed_supermature or 0
    flunked_supermature = flunked_supermature or 0
    learned = learned or 0
    relearned = relearned or 0
    thetime = thetime or 0
    try:
        temp = "%0.1f%%" %(passed/float(passed+flunked)*100)
    except ZeroDivisionError:
        temp = "N/A"
    try:
        temp_supermature = "%0.1f%%" %(passed_supermature/float(passed_supermature+flunked_supermature)*100)
    except ZeroDivisionError:
        temp_supermature = "N/A"
    try:
        again = "%0.1f%%" %(((failed)/(cards))*100)
    except ZeroDivisionError:
        again = "N/A"

    """Calculate progress using weights and card counts from the sched."""
    # Get studdied cards  and true retention stats. YESTERDAY'S VALUES
    
    x = (mw.col.sched.day_cutoff - 86400*2)*1000
    y = (mw.col.sched.day_cutoff - 86400)*1000
    
    xcards, xfailed, xdistinct, xflunked, xpassed, xpassed_supermature, xflunked_supermature, xthetime = mw.col.db.first("""
    select
    sum(case when ease >=1 then 1 else 0 end), /* xcards */
    sum(case when ease = 1 then 1 else 0 end), /* xfailed */
    count(distinct cid), /* xdistinct */
    sum(case when ease = 1 and type == 1 then 1 else 0 end), /* xflunked */
    sum(case when ease > 1 and type == 1 then 1 else 0 end), /* xpassed */
    sum(case when ease > 1 and type == 1 and lastIvl >= 100 then 1 else 0 end), /* xpassed_supermature */
    sum(case when ease = 1 and type == 1 and lastIvl >= 100 then 1 else 0 end), /* xflunked_supermature */
    sum(time)/1000 /* xthetime */
    from revlog where id between ? and ?""",x,y)
    xthetime = xthetime or 0
    xcards = xcards or 0
    xfailed = xfailed or 0
    xdistinct = xdistinct or 0
    xflunked = xflunked or 0
    xpassed = xpassed or 0
    xpassed_supermature = xpassed_supermature or 0
    xflunked_supermature = xflunked_supermature or 0

    xsecspeed = max(1, xthetime)/max(1, xcards)

    try:
        xtemp = "%0.1f%%" %(xpassed/float(xpassed+xflunked)*100)
    except ZeroDivisionError:
        xtemp = "N/A"
    try:
        xtemp_supermature = "%0.1f%%" %(xpassed_supermature/float(xpassed_supermature+xflunked_supermature)*100)
    except ZeroDivisionError:
        xtemp_supermature = "N/A"
    
    """Calculate progress using weights and card counts from the sched."""
    # Get studdied cards  and true retention stats. TWO DAY AVERAGE VALUES
    
    x = (mw.col.sched.day_cutoff - 86400*2)*1000
    
    ycards, yfailed, ydistinct, yflunked, ypassed = mw.col.db.first("""
    select
    sum(case when ease >=1 then 1 else 0 end), /* ycards */
    sum(case when ease = 1 then 1 else 0 end), /* yfailed */
    count(distinct cid), /* ydistinct */
    sum(case when ease = 1 and type == 1 then 1 else 0 end), /* yflunked */
    sum(case when ease > 1 and type == 1 then 1 else 0 end) /* ypassed */
    from revlog where id > ? """,x)
    ycards = ycards or 0
    yfailed = yfailed or 0
    ydistinct = ydistinct or 0
    yflunked = yflunked or 0
    ypassed = ypassed or 0
    
    # YESTERDAY'S VALUES
    zTR = 1-float(xpassed/(float((max(1,xpassed+xflunked)))))
    zagain = float((xfailed)/max(1,(xcards-xpassed)))
    
    # TWO DAY AVERAGE VALUES
    yTR = 1-float(ypassed/(float(max(1,ypassed+yflunked))))
    xagain = float((yfailed)/max(1,(ycards-ypassed)))
    
    # TODAY'S VALUES
    xTR = 1-float(passed/(float(max(1,passed+flunked))))
    yagain = float((failed)/max(1,(cards-passed)))
    
    # TODAY'S VALUES
    xlrnWeight = float((1+(1*yagain*lrnSteps))/1)
    xnewWeight = float((1+(1*yagain*lrnSteps))/1)
    xrevWeight = float((1+(1*xTR*lrnSteps))/1)

    # YESTERDAY'S VALUES
    lrnWeight = float((1+(1*zagain*lrnSteps))/1)
    newWeight = float((1+(1*zagain*lrnSteps))/1)
    revWeight = float((1+(1*zTR*lrnSteps))/1)

    #TWO DAY AVERAGE VALUES
    ylrnWeight = float((1+(1*xagain*lrnSteps))/1)
    ynewWeight = float((1+(1*xagain*lrnSteps))/1)
    yrevWeight = float((1+(1*yTR*lrnSteps))/1)

    """Update progress bar range and value with currDID, totalCount[] and doneCount[]"""      
    pbMax = pbValue = 0
    # Sum top-level decks
    for node in mw.col.sched.deck_due_tree().children:
        pbMax += totalCount[node.deck_id]
        pbValue += doneCount[node.deck_id]  
    
    # showInfo("pbMax = %d, pbValue = %d" % (pbMax, pbValue))
    var_diff = int(pbMax - pbValue)
    progbarmax=var_diff+cards

    speed   = (cards / max(1, thetime))*60
    secspeed = max(1, thetime)/max(1, cards)
    hr = (var_diff / max(1, speed))/60

    x = math.floor(thetime/3600)
    y = math.floor((thetime-(x*3600))/60)
    secs = (thetime-(x*3600))-(y*60)
    hrhr = math.floor(hr)
    hrmin = math.floor(60*(hr-hrhr))
    hrsec = ((hr-hrhr)*60-hrmin)*60

    dt=datetime.today()
    tz = 8 #GMT+ <CHANGE THIS TO YOUR GMT+_ (negative number if you're GMT-)>
    tzsec = tz*3600

    t = timedelta(hours = hrhr, minutes = hrmin, seconds = hrsec)
    left = dt.timestamp()+tzsec+t.total_seconds()

    date_time = datetime.utcfromtimestamp(left).strftime('%Y-%m-%d %H:%M:%S')
    date_time_24H = datetime.strptime(date_time, "%Y-%m-%d %H:%M:%S")
    ETA = date_time_24H.strftime("%I:%M %p")
    
    if pbMax == 0:  # 100%
        progressBar.setRange(0, 1)
        progressBar.setValue(1)
    else:
        progressBar.setRange(0, progbarmax)
        progressBar.setValue(cards)
        
    if showNumber:
        if showDebug:
            if showYesterday:
                if showSuperMatureRetention:
                    if showAgain:
                        if showRetention:
                            if showPercent:
                                percent = 100 if pbMax == 0 else (100 * cards / progbarmax)
                                percentdiff = (100-percent)
                                progressBar.setFormat("%d (%.02f%%) done     |     %d (%.02f%%) left     |     %.02f (%.02f) s/card    |     %s (%.01f%%) AR     |     %s (%s) TR     |     %s (%s) SMTR     |     %02d:%02d spent     |     %02d:%02d more     |     ETA %s     |     %.02f [%.02f] (%.02f) New/Lrn Weight     |     %.02f [%.02f] (%.02f) Rev Weight"  % (cards, percent, var_diff, percentdiff,  secspeed, xsecspeed, again, (zagain*100), temp, xtemp, temp_supermature, xtemp_supermature, x, y, hrhr, hrmin, ETA, xlrnWeight, ylrnWeight, lrnWeight, xrevWeight, yrevWeight, revWeight))
                            else:
                                progressBar.setFormat("%d done     |     %d left     |     %.02f (%.02f) s/card    |     %s (%.01f%%) AR     |     %s (%s) TR     |     %s (%s) SMTR     |     %02d:%02d spent     |     %02d:%02d more     |     ETA %s     |     %.02f [%.02f] (%.02f) New/Lrn Weight     |     %.02f [%.02f] (%.02f) Rev Weight"  % (cards, var_diff,  secspeed, xsecspeed, again, (zagain*100), temp, xtemp, temp_supermature, xtemp_supermature, x, y, hrhr, hrmin, ETA, xlrnWeight, ylrnWeight, lrnWeight, xrevWeight, yrevWeight, revWeight))
                        else:
                            if showPercent:
                                percent = 100 if pbMax == 0 else (100 * cards / progbarmax)
                                percentdiff = (100-percent)
                                progressBar.setFormat("%d (%.02f%%) done     |     %d (%.02f%%) left     |     %.02f (%.02f) s/card    |     %s (%.01f%%) AR     |     %02d:%02d spent     |     %02d:%02d more     |     ETA %s     |     %.02f [%.02f] (%.02f) New/Lrn Weight     |     %.02f [%.02f] (%.02f) Rev Weight"  % (cards, percent, var_diff, percentdiff,  secspeed, xsecspeed, again, (zagain*100), x, y, hrhr, hrmin, ETA, xlrnWeight, ylrnWeight, lrnWeight, xrevWeight, yrevWeight, revWeight))
                            else:
                                progressBar.setFormat("%d done     |     %d left     |     %.02f (%.02f) s/card    |     %s (%.01f%%) AR     |     %02d:%02d spent     |     %02d:%02d more     |     ETA %s     |     %.02f [%.02f] (%.02f) New/Lrn Weight     |     %.02f [%.02f] (%.02f) Rev Weight"  % (cards, var_diff,  secspeed, xsecspeed, again, (zagain*100), x, y, hrhr, hrmin, ETA, xlrnWeight, ylrnWeight, lrnWeight, xrevWeight, yrevWeight, revWeight))
                    else:
                        if showRetention:
                            if showPercent:
                                percent = 100 if pbMax == 0 else (100 * cards / progbarmax)
                                percentdiff = (100-percent)
                                progressBar.setFormat("%d (%.02f%%) done     |     %d (%.02f%%) left     |     %.02f (%.02f) s/card     |     %s (%s) TR     |     %s (%s) SMTR     |     %02d:%02d spent     |     %02d:%02d more     |     ETA %s     |     %.02f [%.02f] (%.02f) New/Lrn Weight     |     %.02f [%.02f] (%.02f) Rev Weight"  % (cards, percent, var_diff, percentdiff,  secspeed, xsecspeed, temp, xtemp, temp_supermature, xtemp_supermature, x, y, hrhr, hrmin, ETA, xlrnWeight, ylrnWeight, lrnWeight, xrevWeight, yrevWeight, revWeight))
                            else:
                                progressBar.setFormat("%d done     |     %d left     |     %.02f (%.02f) s/card     |     %s (%s) TR     |     %s (%s) SMTR     |     %02d:%02d spent     |     %02d:%02d more     |     ETA %s     |     %.02f [%.02f] (%.02f) New/Lrn Weight     |     %.02f [%.02f] (%.02f) Rev Weight"  % (cards, var_diff,  secspeed, xsecspeed, temp, xtemp, temp_supermature, xtemp_supermature, x, y, hrhr, hrmin, ETA, xlrnWeight, ylrnWeight, lrnWeight, xrevWeight, yrevWeight, revWeight))
                        else:
                            if showPercent:
                                percent = 100 if pbMax == 0 else (100 * cards / progbarmax)
                                percentdiff = (100-percent)
                                progressBar.setFormat("%d (%.02f%%) done     |     %d (%.02f%%) left     |     %.02f (%.02f) s/card     |     %02d:%02d spent     |     %02d:%02d more     |     ETA %s     |     %.02f [%.02f] (%.02f) New/Lrn Weight     |     %.02f [%.02f] (%.02f) Rev Weight"  % (cards, percent, var_diff, percentdiff,  secspeed, xsecspeed, x, y, hrhr, hrmin, ETA, xlrnWeight, ylrnWeight, lrnWeight, xrevWeight, yrevWeight, revWeight))
                            else:
                                progressBar.setFormat("%d done     |     %d left     |     %.02f (%.02f) s/card     |     %02d:%02d spent     |     %02d:%02d more     |     ETA %s     |     %.02f [%.02f] (%.02f) New/Lrn Weight     |     %.02f [%.02f] (%.02f) Rev Weight"  % (cards, var_diff,  secspeed, xsecspeed, x, y, hrhr, hrmin, ETA, xlrnWeight, ylrnWeight, lrnWeight, xrevWeight, yrevWeight, revWeight))
                else:
                    if showAgain:
                        if showRetention:
                            if showPercent:
                                percent = 100 if pbMax == 0 else (100 * cards / progbarmax)
                                percentdiff = (100-percent)
                                progressBar.setFormat("%d (%.02f%%) done     |     %d (%.02f%%) left     |     %.02f (%.02f) s/card    |     %s (%.01f%%) AR     |     %s (%s) TR     |     %02d:%02d spent     |     %02d:%02d more     |     ETA %s     |     %.02f [%.02f] (%.02f) New/Lrn Weight     |     %.02f [%.02f] (%.02f) Rev Weight"  % (cards, percent, var_diff, percentdiff,  secspeed, xsecspeed, again, (zagain*100), temp, xtemp, x, y, hrhr, hrmin, ETA, xlrnWeight, ylrnWeight, lrnWeight, xrevWeight, yrevWeight, revWeight))
                            else:
                                progressBar.setFormat("%d done     |     %d left     |     %.02f (%.02f) s/card    |     %s (%.01f%%) AR     |     %s (%s) TR     |     %02d:%02d spent     |     %02d:%02d more     |     ETA %s     |     %.02f [%.02f] (%.02f) New/Lrn Weight     |     %.02f [%.02f] (%.02f) Rev Weight"  % (cards, var_diff,  secspeed, xsecspeed, again, (zagain*100), temp, xtemp, x, y, hrhr, hrmin, ETA, xlrnWeight, ylrnWeight, lrnWeight, xrevWeight, yrevWeight, revWeight))
                        else:
                            if showPercent:
                                percent = 100 if pbMax == 0 else (100 * cards / progbarmax)
                                percentdiff = (100-percent)
                                progressBar.setFormat("%d (%.02f%%) done     |     %d (%.02f%%) left     |     %.02f (%.02f) s/card    |     %s (%.01f%%) AR     |     %02d:%02d spent     |     %02d:%02d more     |     ETA %s     |     %.02f [%.02f] (%.02f) New/Lrn Weight     |     %.02f [%.02f] (%.02f) Rev Weight"  % (cards, percent, var_diff, percentdiff,  secspeed, xsecspeed, again, (zagain*100), x, y, hrhr, hrmin, ETA, xlrnWeight, ylrnWeight, lrnWeight, xrevWeight, yrevWeight, revWeight))
                            else:
                                progressBar.setFormat("%d done     |     %d left     |     %.02f (%.02f) s/card    |     %s (%.01f%%) AR     |     %02d:%02d spent     |     %02d:%02d more     |     ETA %s     |     %.02f [%.02f] (%.02f) New/Lrn Weight     |     %.02f [%.02f] (%.02f) Rev Weight"  % (cards, var_diff,  secspeed, xsecspeed, again, (zagain*100), x, y, hrhr, hrmin, ETA, xlrnWeight, ylrnWeight, lrnWeight, xrevWeight, yrevWeight, revWeight))
                    else:
                        if showRetention:
                            if showPercent:
                                percent = 100 if pbMax == 0 else (100 * cards / progbarmax)
                                percentdiff = (100-percent)
                                progressBar.setFormat("%d (%.02f%%) done     |     %d (%.02f%%) left     |     %.02f (%.02f) s/card     |     %s (%s) TR     |     %02d:%02d spent     |     %02d:%02d more     |     ETA %s     |     %.02f [%.02f] (%.02f) New/Lrn Weight     |     %.02f [%.02f] (%.02f) Rev Weight"  % (cards, percent, var_diff, percentdiff,  secspeed, xsecspeed, temp, xtemp, x, y, hrhr, hrmin, ETA, xlrnWeight, ylrnWeight, lrnWeight, xrevWeight, yrevWeight, revWeight))
                            else:
                                progressBar.setFormat("%d done     |     %d left     |     %.02f (%.02f) s/card     |     %s (%s) TR     |     %02d:%02d spent     |     %02d:%02d more     |     ETA %s     |     %.02f [%.02f] (%.02f) New/Lrn Weight     |     %.02f [%.02f] (%.02f) Rev Weight"  % (cards, var_diff,  secspeed, xsecspeed, temp, xtemp, x, y, hrhr, hrmin, ETA, xlrnWeight, ylrnWeight, lrnWeight, xrevWeight, yrevWeight, revWeight))
                        else:
                            if showPercent:
                                percent = 100 if pbMax == 0 else (100 * cards / progbarmax)
                                percentdiff = (100-percent)
                                progressBar.setFormat("%d (%.02f%%) done     |     %d (%.02f%%) left     |     %.02f (%.02f) s/card     |     %02d:%02d spent     |     %02d:%02d more     |     ETA %s     |     %.02f [%.02f] (%.02f) New/Lrn Weight     |     %.02f [%.02f] (%.02f) Rev Weight"  % (cards, percent, var_diff, percentdiff,  secspeed, xsecspeed, x, y, hrhr, hrmin, ETA, xlrnWeight, ylrnWeight, lrnWeight, xrevWeight, yrevWeight, revWeight))
                            else:
                                progressBar.setFormat("%d done     |     %d left     |     %.02f (%.02f) s/card     |     %02d:%02d spent     |     %02d:%02d more     |     ETA %s     |     %.02f [%.02f] (%.02f) New/Lrn Weight     |     %.02f [%.02f] (%.02f) Rev Weight"  % (cards, var_diff,  secspeed, xsecspeed, x, y, hrhr, hrmin, ETA, xlrnWeight, ylrnWeight, lrnWeight, xrevWeight, yrevWeight, revWeight))
            else:
                if showSuperMatureRetention:
                    if showAgain:
                        if showRetention:
                            if showPercent:
                                percent = 100 if pbMax == 0 else (100 * cards / progbarmax)
                                percentdiff = (100-percent)
                                progressBar.setFormat("%d (%.02f%%) done     |     %d (%.02f%%) left     |     %.02f s/card    |     %s AR     |     %s TR     |     %s SMTR     |     %02d:%02d spent     |     %02d:%02d more     |     ETA %s     |     %.02f New/Lrn Weight     |     %.02f Rev Weight"  % (cards, percent, var_diff, percentdiff,  secspeed, again, temp, temp_supermature, x, y, hrhr, hrmin, ETA, xlrnWeight, xrevWeight))
                            else:
                                progressBar.setFormat("%d done     |     %d left     |     %.02f s/card    |     %s AR     |     %s TR     |     %s SMTR     |     %02d:%02d spent     |     %02d:%02d more     |     ETA %s     |     %.02f New/Lrn Weight     |     %.02f Rev Weight"  % (cards, var_diff,  secspeed, again, temp, temp_supermature, x, y, hrhr, hrmin, ETA, xlrnWeight, xrevWeight))
                        else:
                            if showPercent:
                                percent = 100 if pbMax == 0 else (100 * cards / progbarmax)
                                percentdiff = (100-percent)
                                progressBar.setFormat("%d (%.02f%%) done     |     %d (%.02f%%) left     |     %.02f s/card    |     %s AR     |     %02d:%02d spent     |     %02d:%02d more     |     ETA %s     |     %.02f New/Lrn Weight     |     %.02f Rev Weight"  % (cards, percent, var_diff, percentdiff,  secspeed, again, x, y, hrhr, hrmin, ETA, xlrnWeight, xrevWeight))
                            else:
                                progressBar.setFormat("%d done     |     %d left     |     %.02f s/card    |     %s AR     |     %02d:%02d spent     |     %02d:%02d more     |     ETA %s     |     %.02f New/Lrn Weight     |     %.02f Rev Weight"  % (cards, var_diff,  secspeed, again, x, y, hrhr, hrmin, ETA, xlrnWeight, xrevWeight))
                    else:
                        if showRetention:
                            if showPercent:
                                percent = 100 if pbMax == 0 else (100 * cards / progbarmax)
                                percentdiff = (100-percent)
                                progressBar.setFormat("%d (%.02f%%) done     |     %d (%.02f%%) left     |     %.02f s/card     |     %s TR     |     %s SMTR     |     %02d:%02d spent     |     %02d:%02d more     |     ETA %s     |     %.02f New/Lrn Weight     |     %.02f Rev Weight"  % (cards, percent, var_diff, percentdiff,  secspeed, temp, temp_supermature, x, y, hrhr, hrmin, ETA, xlrnWeight, xrevWeight))
                            else:
                                progressBar.setFormat("%d done     |     %d left     |     %.02f s/card     |     %s TR     |     %s SMTR     |     %02d:%02d spent     |     %02d:%02d more     |     ETA %s     |     %.02f New/Lrn Weight     |     %.02f Rev Weight"  % (cards, var_diff,  secspeed, temp, temp_supermature, x, y, hrhr, hrmin, ETA, xlrnWeight, xrevWeight))
                        else:
                            if showPercent:
                                percent = 100 if pbMax == 0 else (100 * cards / progbarmax)
                                percentdiff = (100-percent)
                                progressBar.setFormat("%d (%.02f%%) done     |     %d (%.02f%%) left     |     %.02f s/card     |     %02d:%02d spent     |     %02d:%02d more     |     ETA %s     |     %.02f New/Lrn Weight     |     %.02f Rev Weight"  % (cards, percent, var_diff, percentdiff,  secspeed, x, y, hrhr, hrmin, ETA, xlrnWeight, xrevWeight))
                            else:
                                progressBar.setFormat("%d done     |     %d left     |     %.02f s/card     |     %02d:%02d spent     |     %02d:%02d more     |     ETA %s     |     %.02f New/Lrn Weight     |     %.02f Rev Weight"  % (cards, var_diff,  secspeed, x, y, hrhr, hrmin, ETA, xlrnWeight, xrevWeight))
                else:
                    if showAgain:
                        if showRetention:
                            if showPercent:
                                percent = 100 if pbMax == 0 else (100 * cards / progbarmax)
                                percentdiff = (100-percent)
                                progressBar.setFormat("%d (%.02f%%) done     |     %d (%.02f%%) left     |     %.02f s/card    |     %s AR     |     %s TR     |     %02d:%02d spent     |     %02d:%02d more     |     ETA %s     |     %.02f New/Lrn Weight     |     %.02f Rev Weight"  % (cards, percent, var_diff, percentdiff,  secspeed, again, temp, x, y, hrhr, hrmin, ETA, xlrnWeight, xrevWeight))
                            else:
                                progressBar.setFormat("%d done     |     %d left     |     %.02f s/card    |     %s AR     |     %s TR     |     %02d:%02d spent     |     %02d:%02d more     |     ETA %s     |     %.02f New/Lrn Weight     |     %.02f Rev Weight"  % (cards, var_diff,  secspeed, again, temp, x, y, hrhr, hrmin, ETA, xlrnWeight, xrevWeight))
                        else:
                            if showPercent:
                                percent = 100 if pbMax == 0 else (100 * cards / progbarmax)
                                percentdiff = (100-percent)
                                progressBar.setFormat("%d (%.02f%%) done     |     %d (%.02f%%) left     |     %.02f s/card    |     %s AR     |     %02d:%02d spent     |     %02d:%02d more     |     ETA %s     |     %.02f New/Lrn Weight     |     %.02f Rev Weight"  % (cards, percent, var_diff, percentdiff,  secspeed, again, x, y, hrhr, hrmin, ETA, xlrnWeight, xrevWeight))
                            else:
                                progressBar.setFormat("%d done     |     %d left     |     %.02f s/card    |     %s AR     |     %02d:%02d spent     |     %02d:%02d more     |     ETA %s     |     %.02f New/Lrn Weight     |     %.02f Rev Weight"  % (cards, var_diff,  secspeed, again, x, y, hrhr, hrmin, ETA, xlrnWeight, xrevWeight))
                    else:
                        if showRetention:
                            if showPercent:
                                percent = 100 if pbMax == 0 else (100 * cards / progbarmax)
                                percentdiff = (100-percent)
                                progressBar.setFormat("%d (%.02f%%) done     |     %d (%.02f%%) left     |     %.02f s/card     |     %s TR     |     %02d:%02d spent     |     %02d:%02d more     |     ETA %s     |     %.02f New/Lrn Weight     |     %.02f Rev Weight"  % (cards, percent, var_diff, percentdiff,  secspeed, temp, x, y, hrhr, hrmin, ETA, xlrnWeight, xrevWeight))
                            else:
                                progressBar.setFormat("%d done     |     %d left     |     %.02f s/card     |     %s TR     |     %02d:%02d spent     |     %02d:%02d more     |     ETA %s     |     %.02f New/Lrn Weight     |     %.02f Rev Weight"  % (cards, var_diff, xsecspeed, temp, x, y, hrhr, hrmin, ETA, xlrnWeight, xrevWeight))
                        else:
                            if showPercent:
                                percent = 100 if pbMax == 0 else (100 * cards / progbarmax)
                                percentdiff = (100-percent)
                                progressBar.setFormat("%d (%.02f%%) done     |     %d (%.02f%%) left     |     %.02f s/card     |     %02d:%02d spent     |     %02d:%02d more     |     ETA %s     |     %.02f New/Lrn Weight     |     %.02f Rev Weight"  % (cards, percent, var_diff, percentdiff,  secspeed, x, y, hrhr, hrmin, ETA, xlrnWeight, xrevWeight))
                            else:
                                progressBar.setFormat("%d done     |     %d left     |     %.02f s/card     |     %02d:%02d spent     |     %02d:%02d more     |     ETA %s     |     %.02f New/Lrn Weight     |     %.02f Rev Weight"  % (cards, var_diff,  secspeed, x, y, hrhr, hrmin, ETA, xlrnWeight, xrevWeight))
        else:
            if showYesterday:
                if showSuperMatureRetention:
                    if showAgain:
                        if showRetention:
                            if showPercent:
                                percent = 100 if pbMax == 0 else (100 * cards / progbarmax)
                                percentdiff = (100-percent)
                                progressBar.setFormat("%d (%.02f%%) done     |     %d (%.02f%%) left     |     %.02f (%.02f) s/card    |     %s (%.01f%%) AR     |     %s (%s) TR     |     %s (%s) SMTR     |     %02d:%02d spent     |     %02d:%02d more     |     ETA %s"  % (cards, percent, var_diff, percentdiff,  secspeed, xsecspeed, again, (zagain*100), temp, xtemp, temp_supermature, xtemp_supermature, x, y, hrhr, hrmin, ETA))
                            else:
                                progressBar.setFormat("%d done     |     %d left     |     %.02f (%.02f) s/card    |     %s (%.01f%%) AR     |     %s (%s) TR     |     %s (%s) SMTR     |     %02d:%02d spent     |     %02d:%02d more     |     ETA %s"  % (cards, var_diff,  secspeed, xsecspeed, again, (zagain*100), temp, xtemp, temp_supermature, xtemp_supermature, x, y, hrhr, hrmin, ETA))
                        else:
                            if showPercent:
                                percent = 100 if pbMax == 0 else (100 * cards / progbarmax)
                                percentdiff = (100-percent)
                                progressBar.setFormat("%d (%.02f%%) done     |     %d (%.02f%%) left     |     %.02f (%.02f) s/card    |     %s (%.01f%%) AR     |     %02d:%02d spent     |     %02d:%02d more     |     ETA %s"  % (cards, percent, var_diff, percentdiff,  secspeed, xsecspeed, again, (zagain*100), x, y, hrhr, hrmin, ETA))
                            else:
                                progressBar.setFormat("%d done     |     %d left     |     %.02f (%.02f) s/card    |     %s (%.01f%%) AR     |     %02d:%02d spent     |     %02d:%02d more     |     ETA %s"  % (cards, var_diff,  secspeed, xsecspeed, again, (zagain*100), x, y, hrhr, hrmin, ETA))
                    else:
                        if showRetention:
                            if showPercent:
                                percent = 100 if pbMax == 0 else (100 * cards / progbarmax)
                                percentdiff = (100-percent)
                                progressBar.setFormat("%d (%.02f%%) done     |     %d (%.02f%%) left     |     %.02f (%.02f) s/card     |     %s (%s) TR     |     %s (%s) SMTR     |     %02d:%02d spent     |     %02d:%02d more     |     ETA %s"  % (cards, percent, var_diff, percentdiff,  secspeed, xsecspeed, temp, xtemp, temp_supermature, xtemp_supermature, x, y, hrhr, hrmin, ETA))
                            else:
                                progressBar.setFormat("%d done     |     %d left     |     %.02f (%.02f) s/card     |     %s (%s) TR     |     %s (%s) SMTR     |     %02d:%02d spent     |     %02d:%02d more     |     ETA %s"  % (cards, var_diff,  secspeed, xsecspeed, temp, xtemp, temp_supermature, xtemp_supermature, x, y, hrhr, hrmin, ETA))
                        else:
                            if showPercent:
                                percent = 100 if pbMax == 0 else (100 * cards / progbarmax)
                                percentdiff = (100-percent)
                                progressBar.setFormat("%d (%.02f%%) done     |     %d (%.02f%%) left     |     %.02f (%.02f) s/card     |     %02d:%02d spent     |     %02d:%02d more     |     ETA %s"  % (cards, percent, var_diff, percentdiff,  secspeed, xsecspeed, x, y, hrhr, hrmin, ETA))
                            else:
                                progressBar.setFormat("%d done     |     %d left     |     %.02f (%.02f) s/card     |     %02d:%02d spent     |     %02d:%02d more     |     ETA %s"  % (cards, var_diff,  secspeed, xsecspeed, x, y, hrhr, hrmin, ETA))
                else:
                    if showAgain:
                        if showRetention:
                            if showPercent:
                                percent = 100 if pbMax == 0 else (100 * cards / progbarmax)
                                percentdiff = (100-percent)
                                progressBar.setFormat("%d (%.02f%%) done     |     %d (%.02f%%) left     |     %.02f (%.02f) s/card    |     %s (%.01f%%) AR     |     %s (%s) TR     |     %02d:%02d spent     |     %02d:%02d more     |     ETA %s"  % (cards, percent, var_diff, percentdiff,  secspeed, xsecspeed, again, (zagain*100), temp, xtemp, x, y, hrhr, hrmin, ETA))
                            else:
                                progressBar.setFormat("%d done     |     %d left     |     %.02f (%.02f) s/card    |     %s (%.01f%%) AR     |     %s (%s) TR     |     %02d:%02d spent     |     %02d:%02d more     |     ETA %s"  % (cards, var_diff,  secspeed, xsecspeed, again, (zagain*100), temp, xtemp, x, y, hrhr, hrmin, ETA))
                        else:
                            if showPercent:
                                percent = 100 if pbMax == 0 else (100 * cards / progbarmax)
                                percentdiff = (100-percent)
                                progressBar.setFormat("%d (%.02f%%) done     |     %d (%.02f%%) left     |     %.02f (%.02f) s/card    |     %s (%.01f%%) AR     |     %02d:%02d spent     |     %02d:%02d more     |     ETA %s"  % (cards, percent, var_diff, percentdiff,  secspeed, xsecspeed, again, (zagain*100), x, y, hrhr, hrmin, ETA))
                            else:
                                progressBar.setFormat("%d done     |     %d left     |     %.02f (%.02f) s/card    |     %s (%.01f%%) AR     |     %02d:%02d spent     |     %02d:%02d more     |     ETA %s"  % (cards, var_diff,  secspeed, xsecspeed, again, (zagain*100), x, y, hrhr, hrmin, ETA))
                    else:
                        if showRetention:
                            if showPercent:
                                percent = 100 if pbMax == 0 else (100 * cards / progbarmax)
                                percentdiff = (100-percent)
                                progressBar.setFormat("%d (%.02f%%) done     |     %d (%.02f%%) left     |     %.02f (%.02f) s/card     |     %s (%s) TR     |     %02d:%02d spent     |     %02d:%02d more     |     ETA %s"  % (cards, percent, var_diff, percentdiff,  secspeed, xsecspeed, temp, xtemp, x, y, hrhr, hrmin, ETA))
                            else:
                                progressBar.setFormat("%d done     |     %d left     |     %.02f (%.02f) s/card     |     %s (%s) TR     |     %02d:%02d spent     |     %02d:%02d more     |     ETA %s"  % (cards, var_diff,  secspeed, xsecspeed, temp, xtemp, x, y, hrhr, hrmin, ETA))
                        else:
                            if showPercent:
                                percent = 100 if pbMax == 0 else (100 * cards / progbarmax)
                                percentdiff = (100-percent)
                                progressBar.setFormat("%d (%.02f%%) done     |     %d (%.02f%%) left     |     %.02f (%.02f) s/card     |     %02d:%02d spent     |     %02d:%02d more     |     ETA %s"  % (cards, percent, var_diff, percentdiff,  secspeed, xsecspeed, x, y, hrhr, hrmin, ETA))
                            else:
                                progressBar.setFormat("%d done     |     %d left     |     %.02f (%.02f) s/card     |     %02d:%02d spent     |     %02d:%02d more     |     ETA %s"  % (cards, var_diff,  secspeed, xsecspeed, x, y, hrhr, hrmin, ETA))
            else:
                if showSuperMatureRetention:
                    if showAgain:
                        if showRetention:
                            if showPercent:
                                percent = 100 if pbMax == 0 else (100 * cards / progbarmax)
                                percentdiff = (100-percent)
                                progressBar.setFormat("%d (%.02f%%) done     |     %d (%.02f%%) left     |     %.02f s/card    |     %s AR     |     %s TR     |     %s SMTR     |     %02d:%02d spent     |     %02d:%02d more     |     ETA %s"  % (cards, percent, var_diff, percentdiff,  secspeed, again, temp, temp_supermature, x, y, hrhr, hrmin, ETA))
                            else:
                                progressBar.setFormat("%d done     |     %d left     |     %.02f s/card    |     %s AR     |     %s TR     |     %s SMTR     |     %02d:%02d spent     |     %02d:%02d more     |     ETA %s"  % (cards, var_diff,  secspeed, again, temp, temp_supermature, x, y, hrhr, hrmin, ETA))
                        else:
                            if showPercent:
                                percent = 100 if pbMax == 0 else (100 * cards / progbarmax)
                                percentdiff = (100-percent)
                                progressBar.setFormat("%d (%.02f%%) done     |     %d (%.02f%%) left     |     %.02f s/card    |     %s AR     |     %02d:%02d spent     |     %02d:%02d more     |     ETA %s"  % (cards, percent, var_diff, percentdiff,  secspeed, again, x, y, hrhr, hrmin, ETA))
                            else:
                                progressBar.setFormat("%d done     |     %d left     |     %.02f s/card    |     %s AR     |     %02d:%02d spent     |     %02d:%02d more     |     ETA %s"  % (cards, var_diff,  secspeed, again, x, y, hrhr, hrmin, ETA))
                    else:
                        if showRetention:
                            if showPercent:
                                percent = 100 if pbMax == 0 else (100 * cards / progbarmax)
                                percentdiff = (100-percent)
                                progressBar.setFormat("%d (%.02f%%) done     |     %d (%.02f%%) left     |     %.02f s/card     |     %s TR     |     %s SMTR     |     %02d:%02d spent     |     %02d:%02d more     |     ETA %s"  % (cards, percent, var_diff, percentdiff,  secspeed, temp, temp_supermature, x, y, hrhr, hrmin, ETA))
                            else:
                                progressBar.setFormat("%d done     |     %d left     |     %.02f s/card     |     %s TR     |     %s SMTR     |     %02d:%02d spent     |     %02d:%02d more     |     ETA %s"  % (cards, var_diff,  secspeed, temp, temp_supermature, x, y, hrhr, hrmin, ETA))
                        else:
                            if showPercent:
                                percent = 100 if pbMax == 0 else (100 * cards / progbarmax)
                                percentdiff = (100-percent)
                                progressBar.setFormat("%d (%.02f%%) done     |     %d (%.02f%%) left     |     %.02f s/card     |     %02d:%02d spent     |     %02d:%02d more     |     ETA %s"  % (cards, percent, var_diff, percentdiff,  secspeed, x, y, hrhr, hrmin, ETA))
                            else:
                                progressBar.setFormat("%d done     |     %d left     |     %.02f s/card     |     %02d:%02d spent     |     %02d:%02d more     |     ETA %s"  % (cards, var_diff,  secspeed, x, y, hrhr, hrmin, ETA))
                else:
                    if showAgain:
                        if showRetention:
                            if showPercent:
                                percent = 100 if pbMax == 0 else (100 * cards / progbarmax)
                                percentdiff = (100-percent)
                                progressBar.setFormat("%d (%.02f%%) done     |     %d (%.02f%%) left     |     %.02f s/card    |     %s AR     |     %s TR     |     %02d:%02d spent     |     %02d:%02d more     |     ETA %s"  % (cards, percent, var_diff, percentdiff,  secspeed, again, temp, x, y, hrhr, hrmin, ETA))
                            else:
                                progressBar.setFormat("%d done     |     %d left     |     %.02f s/card    |     %s AR     |     %s TR     |     %02d:%02d spent     |     %02d:%02d more     |     ETA %s"  % (cards, var_diff,  secspeed, again, temp, x, y, hrhr, hrmin, ETA))
                        else:
                            if showPercent:
                                percent = 100 if pbMax == 0 else (100 * cards / progbarmax)
                                percentdiff = (100-percent)
                                progressBar.setFormat("%d (%.02f%%) done     |     %d (%.02f%%) left     |     %.02f s/card    |     %s AR     |     %02d:%02d spent     |     %02d:%02d more     |     ETA %s"  % (cards, percent, var_diff, percentdiff,  secspeed, again, x, y, hrhr, hrmin, ETA))
                            else:
                                progressBar.setFormat("%d done     |     %d left     |     %.02f s/card    |     %s AR     |     %02d:%02d spent     |     %02d:%02d more     |     ETA %s"  % (cards, var_diff,  secspeed, again, x, y, hrhr, hrmin, ETA))
                    else:
                        if showRetention:
                            if showPercent:
                                percent = 100 if pbMax == 0 else (100 * cards / progbarmax)
                                percentdiff = (100-percent)
                                progressBar.setFormat("%d (%.02f%%) done     |     %d (%.02f%%) left     |     %.02f s/card     |     %s TR     |     %02d:%02d spent     |     %02d:%02d more     |     ETA %s"  % (cards, percent, var_diff, percentdiff,  secspeed, temp, x, y, hrhr, hrmin, ETA))
                            else:
                                progressBar.setFormat("%d done     |     %d left     |     %.02f s/card     |     %s TR     |     %02d:%02d spent     |     %02d:%02d more     |     ETA %s"  % (cards, var_diff, xsecspeed, temp, x, y, hrhr, hrmin, ETA))
                        else:
                            if showPercent:
                                percent = 100 if pbMax == 0 else (100 * cards / progbarmax)
                                percentdiff = (100-percent)
                                progressBar.setFormat("%d (%.02f%%) done     |     %d (%.02f%%) left     |     %.02f s/card     |     %02d:%02d spent     |     %02d:%02d more     |     ETA %s"  % (cards, percent, var_diff, percentdiff,  secspeed, x, y, hrhr, hrmin, ETA))
                            else:
                                progressBar.setFormat("%d done     |     %d left     |     %.02f s/card     |     %02d:%02d spent     |     %02d:%02d more     |     ETA %s"  % (cards, var_diff,  secspeed, x, y, hrhr, hrmin, ETA))
    nmApplyStyle()
    
def setScrollingPB() -> None:
    """Make progress bar in waiting style if the state is resetRequired (happened after editing cards.)"""
    progressBar.setRange(0, 0)
    if showNumber:
        progressBar.setFormat("Waiting...")
    nmApplyStyle()

def nmApplyStyle() -> None:
    """Checks whether Night_Mode is disabled:
        if so, we remove the separator here."""
    global nmStyleApplied
    if not nmUnavailable:
        nmStyleApplied = Night_Mode.nm_state_on
    if not nmStyleApplied:
        mw.setStyleSheet(
            '''
        QMainWindow::separator
    {
        width: 0px;
        height: 0px;
    }
    ''')

def calcProgress(rev: int, lrn: int, new: int) -> int:
    if useToday:
        y = (mw.col.sched.day_cutoff - 86400)*1000

        """Calculate progress using weights and card counts from the sched."""
        # Get studdied cards  and true retention stats
        xcards, xfailed, xdistinct, xflunked, xpassed = mw.col.db.first("""
        select
        sum(case when ease >=1 then 1 else 0 end), /* xcards */
        sum(case when ease = 1 then 1 else 0 end), /* xfailed */
        count(distinct cid), /* xdistinct */
        sum(case when ease = 1 and type == 1 then 1 else 0 end), /* xflunked */
        sum(case when ease > 1 and type == 1 then 1 else 0 end) /* xpassed */
        from revlog where id > ?""",y)
        xcards = xcards or 0
        xfailed = xfailed or 0
        xdistinct = xdistinct or 0
        xflunked = xflunked or 0
        xpassed = xpassed or 0

        TR = 1-float(xpassed/(float(max(1,xpassed+xflunked))))
        xagain = float((xfailed)/max(1,(xcards-xpassed)))
        lrnWeight = float((1+(1*xagain*lrnSteps))/1)
        newWeight = float((1+(1*xagain*lrnSteps))/1)
        revWeight = float((1+(1*TR*lrnSteps))/1)

        ret = 0
        if includeRev:
            ret += rev * revWeight
        if includeLrn:
            ret += lrn * lrnWeight
        if includeNew or (includeNewAfterRevs and rev == 0):
            ret += new * newWeight
        return ret
    if useAverage:
        x = (mw.col.sched.day_cutoff - 86400*2)*1000

        """Calculate progress using weights and card counts from the sched."""
        # Get studdied cards  and true retention stats
        xcards, xfailed, xdistinct, xflunked, xpassed = mw.col.db.first("""
        select
        sum(case when ease >=1 then 1 else 0 end), /* xcards */
        sum(case when ease = 1 then 1 else 0 end), /* xfailed */
        count(distinct cid), /* xdistinct */
        sum(case when ease = 1 and type == 1 then 1 else 0 end), /* xflunked */
        sum(case when ease > 1 and type == 1 then 1 else 0 end) /* xpassed */
        from revlog where id > ?""",x)
        xcards = xcards or 0
        xfailed = xfailed or 0
        xdistinct = xdistinct or 0
        xflunked = xflunked or 0
        xpassed = xpassed or 0

        TR = 1-float(xpassed/(float(max(1,xpassed+xflunked))))
        xagain = float((xfailed)/max(1,(xcards-xpassed)))
        lrnWeight = float((1+(1*xagain*lrnSteps))/1)
        newWeight = float((1+(1*xagain*lrnSteps))/1)
        revWeight = float((1+(1*TR*lrnSteps))/1)

        ret = 0
        if includeRev:
            ret += rev * revWeight
        if includeLrn:
            ret += lrn * lrnWeight
        if includeNew or (includeNewAfterRevs and rev == 0):
            ret += new * newWeight
        return ret
    if useYesterday:     
        x = (mw.col.sched.day_cutoff - 86400*2)*1000
        y = (mw.col.sched.day_cutoff - 86400)*1000

        """Calculate progress using weights and card counts from the sched."""
        # Get studdied cards  and true retention stats
        xcards, xfailed, xdistinct, xflunked, xpassed = mw.col.db.first("""
        select
        sum(case when ease >=1 then 1 else 0 end), /* xcards */
        sum(case when ease = 1 then 1 else 0 end), /* xfailed */
        count(distinct cid), /* xdistinct */
        sum(case when ease = 1 and type == 1 then 1 else 0 end), /* xflunked */
        sum(case when ease > 1 and type == 1 then 1 else 0 end) /* xpassed */
        from revlog where id between ? and ?""",x,y)
        xcards = xcards or 0
        xfailed = xfailed or 0
        xdistinct = xdistinct or 0
        xflunked = xflunked or 0
        xpassed = xpassed or 0

        TR = 1-float(xpassed/(float(max(1,xpassed+xflunked))))
        xagain = float((xfailed)/max(1,(xcards-xpassed)))
        lrnWeight = float((1+(1*xagain*lrnSteps))/1)
        newWeight = float((1+(1*xagain*lrnSteps))/1)
        revWeight = float((1+(1*TR*lrnSteps))/1)

        ret = 0
        if includeRev:
            ret += rev * revWeight
        if includeLrn:
            ret += lrn * lrnWeight
        if includeNew or (includeNewAfterRevs and rev == 0):
            ret += new * newWeight
        return ret

def updateCountsForAllDecks(updateTotal: bool) -> None:
    """
    Update counts.
    After adding, editing or deleting cards (afterStateChange hook), updateTotal should be set to True to update
    totalCount[] based on doneCount[] and remainCount[]. No card should have been answered before this hook is
    triggered, so the change in remainCount[] should be caused by editing collection and therefore goes into
    totalCount[].
    When the user answer a card (showQuestion hook), updateTotal should be set to False to update doneCount[] based on
    totalCount[] and remainCount[]. No change to collection should have been made before this hook is
    triggered, so the change in remainCount[] should be caused by answering cards and therefore goes into
    doneCount[].
    In the later case, remainCount[] may still increase based on the weights of New, Lrn and Rev cards (see comments
    of "Calculation weights" above), in which case totalCount[] may still get updated based on forceForward setting.
    :param updateTotal: True for afterStateChange hook, False for showQuestion hook
    """

    for node in mw.col.sched.deck_due_tree().children:
        updateCountsForTree(node, updateTotal)

def updateCountsForTree(node, updateTotal: bool) -> None:
    did = node.deck_id
    remain = calcProgress(node.review_count, node.learn_count, node.new_count)

    updateCountsForDeck(did, remain, updateTotal)

    for child in node.children:
        updateCountsForTree(child, updateTotal)

def updateCountsForDeck(did: int, remain: int, updateTotal: bool):
    if did not in totalCount.keys():
        totalCount[did] = remainCount[did] = remain
        doneCount[did] = 0
    else:
        remainCount[did] = remain
        if updateTotal:
            totalCount[did] = doneCount[did] + remainCount[did]
        else:
            if remainCount[did] + doneCount[did] > totalCount[did]:
                # This may happen if you press 'again' followed by 'good' for a new card, as stated in comments
                # "Calculation weights,' or when you undo a card, making remaining count increases.

                if forceForward:
                    pass  # give up changing counts, until the remainCount decrease.
                else:
                    totalCount[did] = doneCount[did] + remainCount[did]
            else:
                doneCount[did] = totalCount[did] - remainCount[did]


def afterStateChangeCallBack(state: str, oldState: str) -> None:
    global currDID

    if state == "resetRequired":
        if scrollingBarWhenEditing:
            setScrollingPB()
        return
    elif state == "deckBrowser":
        # initPB() has to be here, since objects are not prepared yet when the add-on is loaded.
        if not progressBar:
            initPB()
            updateCountsForAllDecks(True)
        currDID = None
    else:  # "overview" or "review"
        # showInfo("mw.col.decks.current()['id'])= %d" % mw.col.decks.current()['id'])
        currDID = mw.col.decks.current()['id']

    # showInfo("updateCountsForAllDecks(True), currDID = %d" % (currDID if currDID else 0))
    updateCountsForAllDecks(True)  # see comments at updateCountsForAllDecks()
    updatePB()

def showQuestionCallBack() -> None:
    # showInfo("updateCountsForAllDecks(False), currDID = %d" % (currDID if currDID else 0))
    updateCountsForAllDecks(False)  # see comments at updateCountsForAllDecks()
    updatePB()

addHook("afterStateChange", afterStateChangeCallBack)
addHook("showQuestion", showQuestionCallBack)

if anki_version.startswith("2.0.x"):
    """Workaround for QSS issue in EditCurrent,
    only necessary on Anki 2.0.x"""

    from aqt.editcurrent import EditCurrent


    def changeStylesheet(*args):
        mw.setStyleSheet('''
            QMainWindow::separator
        {
            width: 0px;
            height: 0px;
        }
        ''')


    def restoreStylesheet(*args):
        mw.setStyleSheet("")


    EditCurrent.__init__ = wrap(
        EditCurrent.__init__, restoreStylesheet, "after")
    EditCurrent.onReset = wrap(
        EditCurrent.onReset, changeStylesheet, "after")
    EditCurrent.onSave = wrap(
        EditCurrent.onSave, changeStylesheet, "afterwards")