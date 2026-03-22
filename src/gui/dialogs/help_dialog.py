"""
Help topics dialog — 6 topics ported from run_autograder.py show_help_menu().
"""
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QVBoxLayout, QListWidget, QListWidgetItem,
    QTextBrowser, QDialogButtonBox,
)
from PySide6.QtCore import Qt

from gui.styles import SPACING_SM

_TOPICS = [
    ("What is an API Token?", """
<h3>What is an API Token?</h3>
<p>An API token is like a special password that allows this program to access
your Canvas account safely.</p>
<p>Think of it like a key that only works for specific tasks:</p>
<ul>
  <li>The program can read your course information</li>
  <li>The program can view student submissions</li>
  <li>The program can enter grades</li>
  <li>But it can't change your personal settings or password</li>
</ul>
<p>Why use a token instead of your Canvas password?</p>
<ul>
  <li><b>More secure</b> — if someone gets the token, they can't access everything in
      your Canvas account</li>
  <li>You can delete/disable the token anytime without changing your password</li>
  <li>The program never sees or stores your actual Canvas password</li>
</ul>
<p><b>Important:</b> Keep your API token private! Don't share it with others, just
like you wouldn't share your password.</p>
"""),

    ("How to Get a Token", """
<h3>How to Get / Change Your Canvas API Token</h3>
<h4>Getting your token for the first time:</h4>
<ol>
  <li>Log in to Canvas at your school's Canvas URL.</li>
  <li>Click on your profile picture or name in the top-left corner.</li>
  <li>Select <b>Settings</b> from the dropdown menu.</li>
  <li>Scroll down to the section called <b>Approved Integrations</b>.</li>
  <li>Click the <b>+ New Access Token</b> button.</li>
  <li>In the popup window:
    <ul>
      <li>Enter a name like <i>Autograder</i> in the Purpose field</li>
      <li>Leave the expiration date blank (or set it far in the future)</li>
      <li>Click <b>Generate Token</b></li>
    </ul>
  </li>
  <li><b>Important: Copy the token immediately!</b> Canvas shows it only once.
      If you close the window you'll need to create a new token.</li>
</ol>
<h4>Changing your token:</h4>
<p>If you need to change your token (e.g. it expired or was lost):</p>
<ol>
  <li>Go to the <b>Settings</b> tab in this application.</li>
  <li>Paste the new token in the API Token field and click Save Settings.</li>
</ol>
"""),

    ("Grading Rationales", """
<h3>What are "Grading Rationales"?</h3>
<p>"Grading Rationales" is the folder where this program saves all the reports
and spreadsheets it creates.</p>
<p>When you run an autograding tool, it creates files like:</p>
<ul>
  <li>Spreadsheets (.xlsx) with student scores</li>
  <li>Reports (.csv) for uploading to Canvas</li>
  <li>Engagement Analysis reports (if you run that check)</li>
</ul>
<p>By default, these files are saved in:</p>
<pre>Documents/Autograder Rationales/</pre>
<p>Inside this folder, files are organized by type:</p>
<ul>
  <li>Academic Dishonesty Reports/</li>
  <li>Discussion Forums/</li>
  <li>Complete-Incomplete Assignments/</li>
</ul>
<p>You can change where files are saved in the <b>Settings</b> tab.</p>
"""),

    ("What is Autograding?", """
<h3>What Does "Autograding" Mean?</h3>
<p>"Autograding" means the computer automatically checks student work and assigns
grades based on rules you've set up.</p>
<p>This program includes three autograding tools:</p>
<h4>1. Discussion Forum Autograder</h4>
<ul>
  <li>Checks if students posted in discussion forums</li>
  <li>Verifies they met requirements (word count, replies, etc.)</li>
  <li>Gives credit for complete participation</li>
</ul>
<h4>2. Complete/Incomplete Autograder</h4>
<ul>
  <li>For assignments graded as Complete or Incomplete</li>
  <li>Checks if student submitted something</li>
  <li>Awards full credit if they turned it in</li>
</ul>
<h4>3. Engagement Analysis</h4>
<ul>
  <li>Analyzes student work for engagement depth and personal connection</li>
  <li>Creates a report for YOU to review</li>
  <li>Does <b>not</b> automatically fail students</li>
  <li>You make the final decision on each case</li>
</ul>
<p><b>Important:</b> These tools help speed up grading, but you should always
review the results before finalizing grades!</p>
"""),

    ("File Cleanup Options", """
<h3>Understanding File Cleanup Options</h3>
<p>Over time, this program creates many files. The cleanup feature helps you
manage old files automatically.</p>
<h4>Three cleanup options:</h4>
<h5>1. None (default)</h5>
<ul>
  <li>All files are kept forever</li>
  <li>You manually delete files when needed</li>
  <li>Best if you want complete control</li>
</ul>
<h5>2. Archive</h5>
<ul>
  <li>Old files are moved to an "Archived" subfolder</li>
  <li>Files are still accessible if you need them</li>
  <li>Keeps your main folders tidy</li>
  <li>Recommended for most users</li>
</ul>
<h5>3. Trash / Recycle Bin</h5>
<ul>
  <li>Old files are moved to your computer's Trash/Recycle Bin</li>
  <li>You can restore them if needed</li>
  <li>Files are permanently deleted when you empty the trash</li>
</ul>
<p>You can set how old files must be before cleanup (default: 180 days) and
which file types to clean up.</p>
<p>Configure in the <b>Settings</b> tab, or run a one-time cleanup from
<b>Tools → Run Cleanup Now…</b></p>
"""),

    ("Troubleshooting", """
<h3>Troubleshooting Common Issues</h3>

<h4>Problem: "Invalid API token" or "Authentication failed"</h4>
<p><b>Solution:</b></p>
<ol>
  <li>Your token may have expired — create a new one in Canvas</li>
  <li>Go to Settings tab and update your token</li>
  <li>Make sure you copied the entire token (no spaces)</li>
</ol>

<h4>Problem: Can't find the output files</h4>
<p><b>Solution:</b></p>
<ol>
  <li>Check the "Grading Rationales" folder in your Documents</li>
  <li>Click <b>Open Output Folder</b> in the toolbar or Settings tab</li>
  <li>Look inside the subfolders (Academic Dishonesty, etc.)</li>
</ol>

<h4>Problem: Program crashes or shows errors</h4>
<p><b>Solution:</b></p>
<ol>
  <li>Make sure you're connected to the internet</li>
  <li>Check that your Canvas site is accessible in a browser</li>
  <li>Try clicking Refresh in the toolbar</li>
  <li>If it keeps failing, check the Canvas URL in Settings</li>
</ol>

<h4>Problem: Grades aren't appearing in Canvas</h4>
<p><b>Solution:</b></p>
<p>The autograder submits grades directly to Canvas via the API. If you used
<b>Dry Run</b> mode, no grades were submitted. Turn off Dry Run and run again
to submit actual grades.</p>

<h4>Problem: Want to change where files are saved</h4>
<p><b>Solution:</b></p>
<ol>
  <li>Go to the <b>Settings</b> tab</li>
  <li>Click <b>Browse…</b> next to the Folder field</li>
  <li>Choose your preferred location and click Save Settings</li>
</ol>
"""),
]


class HelpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Help")
        self.setMinimumSize(700, 500)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(SPACING_SM)

        split = QHBoxLayout()

        self._topic_list = QListWidget()
        self._topic_list.setMaximumWidth(200)
        for title, _ in _TOPICS:
            self._topic_list.addItem(QListWidgetItem(title))
        self._topic_list.currentRowChanged.connect(self._show_topic)
        split.addWidget(self._topic_list)

        self._browser = QTextBrowser()
        self._browser.setOpenExternalLinks(True)
        split.addWidget(self._browser, 1)

        layout.addLayout(split)

        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btn_box.rejected.connect(self.accept)
        layout.addWidget(btn_box)

        self._topic_list.setCurrentRow(0)

    def _show_topic(self, row: int) -> None:
        if 0 <= row < len(_TOPICS):
            _, html = _TOPICS[row]
            self._browser.setHtml(html)
