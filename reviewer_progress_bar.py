from __future__ import unicode_literals
from typing import Optional
from .nightmode import isnightmode

from anki.hooks import addHook, wrap
from anki import version as anki_version

from aqt.qt import *
from aqt import mw

import math

from datetime import datetime, timedelta

from aqt import gui_hooks

# -------------Configuration------------------
config = mw.addonManager.getConfig(__name__)

############## USER CONFIGURATION START ##############

# CARD TALLY CALCULATION

# Which queues to include in the progress calculation (all True by default)
includeNew = 0
includeRev = 1
includeLrn = 1

# Only include new cards once reviews are exhausted.
includeNewAfterRevs = 0

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

# If enabled, the progress will freeze if remaining count has to increase to prevent moving backward,
#   and wait until your correct answers 'make up' this additional part.
#   NOTE: This will not stop the progress from moving backward if you add cards or toggle suspended.
forceForward = 0

# PROGRESS BAR APPEARANCE

lrn_steps = config['lrn_steps']
#rlrn_steps = config['rlrn_steps']
no_days = config['no_days']
tz = config['tz']  # GMT+ <CHANGE THIS TO YOUR GMT+_ (negative number if you're GMT-)>
show_percent = config['show_percent']  # DEFAULT: 1 Show the progress text percentage or not.
show_retention = config['show_retention']  # DEFAULT: 1 Show the retention or not.
show_super_mature_retention = config['show_super_mature_retention']  # DEFAULT: 1 Show Super Mature Retention
show_again = config['show_again']  # DEFAULT: 1 Show again rate or not
show_number = config['show_number']  # DEFAULT: 1 Show the progress text as a fraction
show_yesterday = config['show_yesterday']  # DEFAULT: 1 Show yesterday's values in parentheses
show_debug = config['show_debug']  # DEFAULT: 0 Show New/Lrn/Rev Weights used for computation

if isnightmode():
    qtxt = "aliceblue"  # Percentage color, if text visible.
    qbg = "rgba(39, 40, 40, 1)"  # Background color of progress bar.
    qfg = "#3399cc"  # Foreground color of progress bar.
    qbr = 0  # Border radius (> 0 for rounded corners).
    qtr = 0  # Border radius (> 0 for rounded corners).
else:
    qtxt = "black"  # Percentage color, if text visible.
    qbg = "rgba(228, 228, 228, 1)"  # Background color of progress bar.
    qfg = "#3399cc"  # Foreground color of progress bar.
    qbr = 0  # Border radius (> 0 for rounded corners).
    qtr = 0  # Border radius (> 0 for rounded corners).

# optionally restricts progress bar width
maxWidth = 20  # (e.g. "5px". default: "")

scrollingBarWhenEditing = 1  # Make the progress bar 'scrolling' when waiting to resume.

orientationHV = Qt.Orientation.Horizontal  # Show bar horizontally (side to side). Use with top/bottom dockArea.
#orientationHV = Qt.Vertical # Show bar vertically (up and down). Use with right/left dockArea.

invertTF = 0  # If set to True, inverts and goes from right to left or top to bottom.

dockArea = Qt.DockWidgetArea.TopDockWidgetArea  # Shows bar at the top. Use with horizontal orientation.
#dockArea = Qt.DockWidgetArea.BottomDockWidgetArea # Shows bar at the bottom. Use with horizontal orientation.
#dockArea = Qt.DockWidgetArea.RightDockWidgetArea # Shows bar at right. Use with vertical orientation.
#dockArea = Qt.DockWidgetArea.LeftDockWidgetArea # Shows bar at left. Use with vertical orientation.

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

lrn_weight = 0
new_weight = 0
rev_weight = 0


def add_info():
    # card types: 0=new, 1=lrn, 2=rev, 3=relrn
    # queue types: 0=new, 1=(re)lrn, 2=rev, 3=day (re)lrn,
    #   4=preview, -1=suspended, -2=sibling buried, -3=manually buried

    # revlog types: 0=lrn, 1=rev, 2=relrn, 3=early review
    # positive revlog intervals are in days (rev), negative in seconds (lrn)
    # odue/odid store original due/did when cards moved to filtered deck
    x = (mw.col.sched.day_cutoff - 86400 * no_days) * 1000
    y = (mw.col.sched.day_cutoff - 86400) * 1000
    """Calculate progress using weights and card counts from the sched."""
    # Get studied cards  and true retention stats
    x_new, x_new_pass, x_learn, x_learn_pass, x_flunked, x_passed = mw.col.db.first("""
                select
                sum(case when ease = 1 and type == 0 and lastIvl == 0 then 1 else 0 end), /* xnew agains */
                sum(case when ease > 1 and type == 0 and lastIvl == 0 then 1 else 0 end), /* xnew pass */
                sum(case when ease = 1 and type in (0, 2) and type != 1 and type != 3 then 1 else 0 end), /* xlearn agains */
                sum(case when ease > 1 and type in (0, 2) and type != 1 and type != 3 then 1 else 0 end), /* xlearn pass */
                sum(case when ease = 1 and type in (1, 3) and type != 0 and type != 2 then 1 else 0 end), /* x_flunked */
                sum(case when ease > 1 and type in (1, 3) and type != 0 and type != 2 then 1 else 0 end) /* x_passed */
                from revlog where id between ? and ?""", x, y)
    x_new = x_new or 0
    x_new_pass = x_new_pass or 0

    x_learn = x_learn or 0
    x_learn_pass = x_learn_pass or 0

    x_flunked = x_flunked or 0
    x_passed = x_passed or 0

    """Calculate progress using weights and card counts from the sched."""

    #retention rate for review cards
    tr = (float(x_flunked / (float(max(1, x_passed + x_flunked)))))

    x_learn_agains = float(x_learn / max(1, (x_learn + x_learn_pass)))
    x_new_agains = float(x_new / max(1, (x_new + x_new_pass)))

    global lrn_weight
    global new_weight
    global rev_weight

    lrn_weight = float((1 + (1 * x_learn_agains * lrn_steps)) / 1)
    new_weight = float((1 + (1 * x_new_agains * lrn_steps)) / 1)
    rev_weight = float((1 + (1 * tr * lrn_steps)) / 1)


gui_hooks.main_window_did_init.append(add_info)


def initPB() -> None:
    """Initialize and set parameters for progress bar, adding it to the dock."""
    global progressBar
    progressBar = QProgressBar()
    progressBar.setTextVisible(show_percent or show_number)
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

    # Note: if there is another widget already in this dock position, we have to add ourselves to the list

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
    # Get studied cards  and true retention stats. TODAY'S VALUES

    a = (mw.col.sched.day_cutoff - 86400) * 1000

    cards, failed, flunked, passed, passed_supermature, flunked_supermature, thetime = mw.col.db.first("""
    select
    sum(case when ease >=1 then 1 else 0 end), /* cards */
    sum(case when ease = 1 then 1 else 0 end), /* failed */
    sum(case when ease = 1 and type == 1 then 1 else 0 end), /* flunked */
    sum(case when ease > 1 and type == 1 then 1 else 0 end), /* passed */
    sum(case when ease > 1 and type == 1 and lastIvl >= 100 then 1 else 0 end), /* passed_supermature */
    sum(case when ease = 1 and type == 1 and lastIvl >= 100 then 1 else 0 end), /* flunked_supermature */
    sum(time)/1000 /* thetime */
    from revlog where id > ? """, a)
    cards = cards or 0
    failed = failed or 0
    flunked = flunked or 0
    passed = passed or 0
    passed_supermature = passed_supermature or 0
    flunked_supermature = flunked_supermature or 0
    thetime = thetime or 0
    try:
        temp = "%0.2f%%" % (passed / float(passed + flunked) * 100)
    except ZeroDivisionError:
        temp = "N/A"
    try:
        temp_supermature = "%0.2f%%" % (passed_supermature / float(passed_supermature + flunked_supermature) * 100)
    except ZeroDivisionError:
        temp_supermature = "N/A"
    try:
        again = "%0.2f%%" % ((failed / cards) * 100)
    except ZeroDivisionError:
        again = "N/A"

    """Calculate progress using weights and card counts from the sched."""
    # Get studdied cards  and true retention stats. AVERAGE VALUES

    d = (mw.col.sched.day_cutoff - 86400 * no_days) * 1000

    ycards, yfailed, yflunked, ypassed, ypassed_supermature, yflunked_supermature, ythetime = mw.col.db.first("""
    select
    sum(case when ease >=1 then 1 else 0 end), /* ycards */
    sum(case when ease = 1 then 1 else 0 end), /* yfailed */
    sum(case when ease = 1 and type == 1 then 1 else 0 end), /* yflunked */
    sum(case when ease > 1 and type == 1 then 1 else 0 end), /* ypassed */
    sum(case when ease > 1 and type == 1 and lastIvl >= 100 then 1 else 0 end), /* xpassed_supermature */
    sum(case when ease = 1 and type == 1 and lastIvl >= 100 then 1 else 0 end), /* xflunked_supermature */
    sum(time)/1000 /* ythetime */
    from revlog where id > ? """, d)
    ycards = ycards or 0
    yfailed = yfailed or 0
    yflunked = yflunked or 0
    ypassed = ypassed or 0
    ypassed_supermature = ypassed_supermature or 0
    yflunked_supermature = yflunked_supermature or 0
    ythetime = ythetime or 0
    ysecspeed = max(1,ythetime)/max(1,ycards)

    try:
        ytemp = "%0.2f%%" % (ypassed / float(ypassed + yflunked) * 100)
    except ZeroDivisionError:
        ytemp = "N/A"
    try:
        ytemp_supermature = "%0.2f%%" % (ypassed_supermature / float(ypassed_supermature + yflunked_supermature) * 100)
    except ZeroDivisionError:
        ytemp_supermature = "N/A"
    try:
        y_again = "%0.2f%%" % ((yfailed / ycards) * 100)
    except ZeroDivisionError:
        y_again = "N/A"

    """Update progress bar range and value with currDID, totalCount[] and doneCount[]"""
    pbMax = pbValue = 0
    # Sum top-level decks
    for node in mw.col.sched.deck_due_tree().children:
        pbMax += totalCount[node.deck_id]
        pbValue += doneCount[node.deck_id]

        # showInfo("pbMax = %d, pbValue = %d" % (pbMax, pbValue))
    var_diff = pbMax - pbValue
    progbarmax = int(var_diff + cards)

    speed = (cards / max(1, thetime)) * 60
    secspeed = max(1, thetime) / max(1, cards)
    hr = (var_diff / max(1, speed)) / 60

    x = math.floor(thetime / 3600)
    y = math.floor((thetime - (x * 3600)) / 60)

    hrhr = math.floor(hr)
    hrmin = math.floor(60 * (hr - hrhr))
    hrsec = ((hr - hrhr) * 60 - hrmin) * 60

    dt = datetime.today()

    tzsec = tz * 3600

    t = timedelta(hours=hrhr, minutes=hrmin, seconds=hrsec)
    left = dt.timestamp() + tzsec + t.total_seconds()

    date_time = datetime.utcfromtimestamp(left).strftime('%Y-%m-%d %H:%M:%S')
    date_time_24H = datetime.strptime(date_time, "%Y-%m-%d %H:%M:%S")
    ETA = date_time_24H.strftime("%I:%M %p")

    if pbMax == 0:  # 100%
        progressBar.setRange(0, 1)
        progressBar.setValue(1)
    else:
        progressBar.setRange(0, progbarmax)
        progressBar.setValue(cards)


    percent = 100 if pbMax == 0 else (100 * cards / progbarmax)
    percentdiff = (100 - percent)

    if show_number:
        if show_percent:
            output = f"{cards} ({percent:.02f}%) done"
            output += f"     |     {var_diff:.0f} ({percentdiff:.02f}%) left"
        else:
            output = f"{cards} done"
            output += f"     |     {var_diff:.0f} left"
        if True==True:
            if show_yesterday: 
                output += f"     |     {secspeed:.02f} ({ysecspeed:.02f}) s/card"
            else: 
                output += f"     |     {secspeed:.02f} s/card"
        if show_again:
            if show_yesterday: 
                output += f"     |     {again} ({y_again}) Again"
            else: 
                output += f"     |     {again} Again"
        if show_retention:
            if show_yesterday: 
                output += f"     |     {temp} ({ytemp}) TR"
            else:
                output += f"     |     {temp} TR"
        if show_super_mature_retention:
            if show_yesterday: 
                output += f"     |     {temp_supermature} ({ytemp_supermature}) SMTR"
            else:
                output += f"     |     {temp_supermature} SMTR"               
        if True==True:
            output += f"     |     {x:02d}:{y:02d} spent"
            output += f"     |     {hrhr:02d}:{hrmin:02d} more"
            ETA = f"{ETA}+1" if hrhr >= 24 else ETA
            output += f"     |     ETA {ETA}"
        if show_debug:
            output += f"     |     {new_weight:.02f} New Weight"
            output += f"     |     {lrn_weight:.02f} Lrn Weight"
            output += f"     |     {rev_weight:.02f} Rev Weight"
    else: output = f""

    progressBar.setFormat(output)
    
    nmApplyStyle()


def setScrollingPB() -> None:
    """Make progress bar in waiting style if the state is resetRequired (happened after editing cards.)"""
    progressBar.setRange(0, 0)
    if show_number:
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

#used to calculate var_diff
def calcProgress(rev: int, lrn: int, new: int) -> int:
    ret = 0
    if includeRev:
        ret += rev * rev_weight
    if includeLrn:
        ret += lrn * lrn_weight
    if includeNew or (includeNewAfterRevs and rev == 0):
        ret += new * new_weight
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
                # 'Calculation weights,' or when you undo a card, making remaining count increases.

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
    elif state == "profileManager":
        # fixes the issue with multiple profiles
        return
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
    
# Define a function to toggle the visibility of the progress bar
def toggleProgressBar():
    global progressBar
    if progressBar.isVisible():
        progressBar.hide()
    else:
        progressBar.show()

# Create a QAction object
action = QAction("Toggle Progress Bar", mw)

# Set the shortcut for the action to Ctrl+G
toggle_sc = config.get('toggle_shortcut', 'Ctrl+G')
shortcut = QKeySequence(toggle_sc)  # Customize the shortcut as needed
action.setShortcut(shortcut)

# Connect the action to the toggleProgressBar function
action.triggered.connect(toggleProgressBar)

# Add the action to the menuTools menu
mw.form.menuTools.addAction(action)
