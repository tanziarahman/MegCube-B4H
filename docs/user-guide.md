# B4H Portal User Guide

How to use the B4H Portal day to day: what each page shows, and how to do common tasks.

> **Who this is for:** security staff, receptionists, site managers and anyone else using the portal. No technical knowledge needed.
> **Installing or fixing the portal** is covered in the [main README](../README.md).

---

## Contents

1. [What the portal does](#1-what-the-portal-does)
2. [Getting started](#2-getting-started)
3. [Finding your way around](#3-finding-your-way-around)
4. [Dashboard](#4-dashboard)
5. [Live view](#5-live-view)
6. [Recognition](#6-recognition)
7. [Captures](#7-captures)
8. [People](#8-people)
9. [Devices](#9-devices)
10. [Time plans](#10-time-plans)
11. [Alarms](#11-alarms)
12. [People counting](#12-people-counting)
13. [Common tasks](#13-common-tasks)
14. [Messages and what to do](#14-messages-and-what-to-do)
15. [Questions](#15-questions)
16. [Glossary](#16-glossary)

---

## 1. What the portal does

Your site has a **B4H box** connected to its cameras. The box watches the video, recognises people it knows, and saves what it sees. The portal is the website for working with the box.

| You want to… | Go to |
|---|---|
| See today at a glance | **Dashboard** |
| Watch cameras live | **Live view** |
| Find who came in, and when | **Recognition** |
| Find unknown visitors (strangers) | **Recognition** |
| Trace someone's movements | **Captures** |
| Register staff or visitors | **People** |
| Add or fix cameras | **Devices** |
| Set working-hours schedules | **Time plans** |
| Get an email when someone is somewhere they shouldn't be | **Alarms** |
| Know how many people walked past a camera | **People counting** |

**Key ideas**

- The **face library** is the box's list of known people, each with a photo.
- A **recognition** (or *match*) is when a camera sees someone from the face library.
- A **stranger** is a face that matches nobody in the library.
- A **capture** is any face or body picture the box saved, recognised or not.
- **Similarity** (0–100): how closely a face matches the library photo.
- **Liveness** (0–100): how likely it's a real person, not a photo held up to the camera.

---

## 2. Getting started

**You need:** a computer on the same network as the box, and Chrome, Edge or Firefox. You also need the portal's address, usually **http://localhost:3000**, or one your administrator gives you.

> Set your computer to the **same time zone as the box**, or times on screen will look shifted.

**Sign in:** type any **Username** and the password `admin`, then click **Sign in**. This is a demo sign-in; individual accounts aren't set up yet.

**Sign out:** click **Admin** (top right) → **Sign out**.

---

## 3. Finding your way around

The **sidebar** on the left groups the pages:

| Group | Pages |
|---|---|
| **Monitor** | Dashboard, Live view |
| **Events** | Alarms, Recognition, Captures, People counting |
| **Manage** | People, Devices, Time plans, Settings (not available yet) |

- The red number next to **Alarms** is the number of open alarms (updated every minute).
- The button left of the search box shrinks the sidebar to icons. Click it again to expand.

The **top bar** has:
- a search box (it only opens the People page for now)
- some indicators that aren't connected to real data yet (*Demo data*, *Devices 20/24*, *Live*)
- a language switch (English only for now)
- **Admin**, for signing out

**Works the same everywhere**

- **Esc** closes windows and side panels.
- **Deleting always asks first, and can't be undone.**
- Errors appear in red, usually with a **Try again** or **Refresh** button.
- **Refresh** reloads the latest data.

---

## 4. Dashboard

**What it's for:** a one-screen summary of **today**. Check it first each day.

It refreshes itself every 45 seconds. Click **Refresh** for the very latest figures. If a refresh fails, the last figures stay on screen with a red note.

The line at the top shows whether the box clock was read (green dot) or not (amber). It also shows where the numbers came from: *portal database* (fast) or *box*. The figures mean the same either way.

| Section | What it shows |
|---|---|
| **Summary cards** | **Recognitions** and **Strangers** today (compared with yesterday), **Cameras** online, and **Captures** (face and body) |
| **People flow** | **Tracked encounters** (each pass by a camera counts once), **unique recognised people**, and **recognised** and **stranger** encounters |
| **Activity by hour** | A bar per hour; the tallest is the **peak hour** |
| **Signals worth checking** | **Average match score**, **low-confidence matches** (similarity under 70; may be wrong matches), **low-liveness matches** (under 80; **someone may have held up a photo**, so investigate), **busiest camera** |
| **Camera readiness** | Each camera: 🟢 **Ready**, 🟡 **Stream issue** (online but no video), 🔴 **Offline** |
| **Attention queue** | Up to 5 problems, most serious first: offline cameras, no video, no analysis task, box clock unreadable, or *Dashboard numbers may be behind* |
| **Recent activity** | Latest matches and strangers. **View records** opens Recognition. |
| **Most recognised today** | The five people seen most |

> *"Trend metrics use the latest N recognition records"* means it was a very busy day: totals are exact, but charts use a sample.

---

## 5. Live view

**What it's for:** watching up to 9 cameras at once.

- **Cameras** (left): 🟢 online, grey offline. *on wall* means it's already showing.
- **Video wall** (middle): choose **Layout 1**, **4** or **9**. Online cameras fill the tiles when the page opens.
- **Latest recognitions** (right): today's newest matches, updated every 5 seconds.

**Show a camera:** click a tile (blue outline), then click the camera in the list. The next tile is selected for you. To move a camera, select another tile and click the camera again.

**Tile buttons** (hover the top of a tile):

| Button | What it does |
|---|---|
| **SD** / **HD** | Lighter video / full quality. Grids use SD; 1-tile layout and full screen use HD. |
| ⟳ | Reconnect a frozen tile |
| ⤢ | Full screen (**Esc** to leave) |
| ✕ | Remove the camera from the tile |

**If something goes wrong**

- *Stream unavailable*: the camera can't be reached, or video conversion isn't set up. Tell your administrator.
- *Too many live videos open*: about 16 videos are already playing across all users. Close some tiles or tabs.

Live video uses a lot of bandwidth, so close the page when you're not watching.

---

## 6. Recognition

**What it's for:** finding **who was recognised, where and when**, and finding **strangers**.

1. Set the filters: **Capture device**, **Recognition result** (**Matched** or **Stranger**), and **From** / **To** (default: today).
2. Click **Search**. **Reset** returns the filters to today, Matched, all cameras.

> **Capture device** only filters the records on the current page, so a page may show fewer than 10 rows.

The table shows 10 records per page: the face, the whole scene, camera, time, liveness, the library photo, name, group and similarity. Click a picture to open it full size.

**Details** (👁): opens a side panel with:
- the captured and library photos
- track ID and liveness
- face attributes (age, glasses, mask…)
- other people it resembled
- the raw record, for support

**Delete** (🗑): removes the record from the box permanently, after you confirm.

> Records of people removed from the face library are hidden. If you see *The box took too long to answer*, shorten the date range.

---

## 7. Captures

**What it's for:** browsing **every face and body** the cameras picked out, recognised or not. Use it to trace someone's movements.

Filters apply as soon as you change them:
- **From** / **To**
- **Target type**: Face or Body
- **Device**
- **Track ID**: one person's path past one camera

> **Device** and **Track ID** only filter the current page. To search a whole day for one track, set the page size to 30 and go through the pages.

Switch between **grid** and **list** view with the icons on the right. Click a picture or **Details** to see the full frame and the attributes the box detected (shown as raw codes for now).

---

## 8. People

**What it's for:** managing the **face library**. Anyone not in it is reported as a stranger.

**Add a person**

1. Click **+ Add person**.
2. Enter a **Name** and choose a **Reference photo** (clear, front-facing, under 5 MB).
3. Optionally add a **Code** (e.g. employee number), **Birthday**, **Groups** and **Remarks**.
4. Click **Add person**. The box starts recognising them.

**Edit** (✎): change details and click **Save changes**.
- Leave the photo empty to keep the current one.
- Ticked groups replace the old ones. If you untick every group, the groups stay as they were.

**Delete** (🗑): removes the person from the box. Their old records are hidden on the Recognition page.

**Tips for good recognition**
- Use a sharp, well-lit, front-facing photo with one face and no sunglasses or hat.
- Use groups (Staff, Visitors…) to tell people apart in records.

---

## 9. Devices

**What it's for:** managing the **cameras** connected to the box.

The page shows:
- counts of cameras online and offline
- filters for name, status and address
- a list or grid of cameras (passwords are never shown)

**Add a camera**

1. Click **+ New device**.
2. Enter a unique **Device name**, and choose **Video** and **RTSP**.
3. Enter the **RTSP address** (starts with `rtsp://`; the camera installer can give it to you), **Username** and **Password**.
4. Click **Add device**.

> **Picture** and **GB28181** devices can't be added from the portal yet. Use the box's own web page for these.

**Edit** (✎): leave **Password** empty to keep the current one.

**Delete** (🗑): the box stops using that camera.

> **Online** but **Not streaming** (grid view) means the box reaches the camera but gets no video. Check the address, username and password.

---

## 10. Time plans

**What it's for:** schedules for **when** the box's rules are active, e.g. office hours.
- **Regular plans** repeat every week.
- **Festival plans** are for holidays.

All times are in the box's time zone.

**Create a plan**

1. Choose the **Regular plans** or **Festival plans** tab, then click **+ New time plan**.
2. Click the name at the top to rename it.
3. Click **+** on each active day. This adds a 09:00–17:00 window; change the times as needed. Add a second window for a split day. Days without windows are off.
4. Click **Save draft** to create it on the box.

**Edit:** select a plan, make changes, click **Save to box**.

**Delete:** click 🗑 next to the save button.

> Unsaved plans and changes are kept only **in your browser**: the box doesn't use them until you save.

---

## 11. Alarms

**What it's for:** getting an **email** when the cameras see someone where or when they shouldn't, e.g. *anyone on camera D3 after 10 pm*. You write the rules; the portal checks every detection against them, usually within about 10 seconds.

> Alarms need the portal's database. If the page says *Alarms need the portal database*, ask your administrator.

The page has three tabs.

### Alarms tab: what happened

Open alarms are shown first. Filter by **Status**, **Rule**, **Camera** and date. The list refreshes every 30 seconds.

Each alarm shows:
- the snapshot and time
- the rule and its severity (**Info**, **Warning**, **Critical**)
- who it was (a name, or **Stranger**)
- its status (**Open**, **Acknowledged**, **Resolved**, **False alarm**)

**Details** (or the link in the email) shows the full camera view, every detection in this alarm, and whether each email was sent. To handle it, type your name and an optional note, then click **Acknowledge**, **Resolve**, **False alarm** or **Reopen**.

### Rules tab: what to watch for

1. Click **+ New rule**. Give it a **name** and **severity**.
2. Tick the **cameras** to watch.
3. Choose **Who triggers it**:
   - **Anyone**. Also tick **Body capture** to catch people whose face isn't visible.
   - **Strangers only**.
   - **Anyone in the face library**.
   - **Specific people or groups**.
4. **When it's active**: **Always**, or **Set times** (days and hours). A window like **22:00 to 06:00** runs past midnight.
5. **Quiet period** (default 5 minutes): after an alarm, more people seen on that camera are added to the same alarm instead of sending more emails.
6. Tick up to **5 recipients**, then click **Create rule**.

The **On** switch pauses a rule. Deleting a rule keeps its past alarms.

### Recipients tab: who gets emailed

- **+ Add recipient** with a name and email.
- Untick *Receives alarm emails* to pause someone.
- Use **Send test** to check emails arrive (look in spam too).

### Warnings at the top of the page

| Warning | Meaning |
|---|---|
| *The portal can't read new detections from the box right now* | The box is unreachable. Alarms catch up when it's back. |
| *Email isn't set up* | Alarms are saved but nobody is emailed. Tell your administrator. |
| *… alarm emails could not be delivered* | Email server problem. Open an alarm to see the error. |

> A person the cameras don't detect can't raise an alarm, so camera angle and lighting matter.

---

## 12. People counting

**What it's for:** seeing **how many people walked past** each camera, and **how many different people** that was. Use it to find busy times and busy cameras.

> People counting needs the portal's database. If the page says so, ask your administrator.

### The numbers

| Number | Meaning | Example |
|---|---|---|
| **Walk-pasts** | One person passing one camera once. The box's several pictures of that pass count as one. | Ada passes the entrance at 9:00 and 13:00 = **2** |
| **Different people** | How many separate people that was. Each person counts once per period. | Ada = **1** |
| **Recognised people** | Different people from the face library | |
| **Strangers** | Passes by people not in the face library. Counts passes, not people. | |

### Why "different people" is an estimate

The box doesn't know who unrecognised people are. So the portal compares each walk-past's **face and clothing** with the others, and treats walk-pasts that look alike as the same person.

This isn't perfect. Two people dressed alike can count as one, and one person in very different light can count as two. That's why the page shows a range, e.g. **≈ 7, likely 6–10**.

- **Multi-day periods count too high**, because people change clothes. Single days are most accurate.
- New walk-pasts take a few seconds to process (*still being processed*).
- Walk-pasts with no usable picture aren't included; the page says how many.
- Very long periods can't be compared; pick a shorter one.

### Filters

| Filter | What it does |
|---|---|
| **Cameras** | Tick cameras. None ticked = all counted cameras. |
| **Period** | Today, Yesterday, Last 7 days, Last 30 days, or **Custom** |
| **Hours** | Only these hours, e.g. 09:00–17:00 (22:00–05:00 runs past midnight) |
| **Weekdays** | Only the ticked days. None ticked = every day. |

Filters are remembered in your browser. **Reset** goes back to Today. With Today selected, the page refreshes every minute.

### On the page

1. **Number tiles**: the numbers above.
2. **Over time**: **New people** (each person once, when first seen) or **Walk-pasts** (every pass). Use **15 min**, **Hour** or **Day** to change the bar size.
3. **Busy times**: weekdays × hours. **Darker = busier** on an average day. Striped squares are days outside the period.
4. **By camera**: numbers per camera.
5. **Walk-pasts**: each pass with its pictures, camera and time. The **Who** column says:
   - **New person**: counted.
   - **Came back**: not counted again.
   - **Can't tell**: no usable picture.
6. **Camera settings**:
   - Untick **Include in counting** to leave a camera out of the totals.
   - Use **What counts** to count only people whose face (or body) was seen. *Everyone* suits most cameras.

> The page doesn't count people **entering or leaving**, or how many are inside right now. The box doesn't record which way people walk.

---

## 13. Common tasks

**Daily check (2 minutes)**
1. Open the **Dashboard**.
2. Check the **Attention queue** and **Camera readiness**: every camera should be 🟢.
3. Check **Strangers** and **Low-liveness matches**. If anything is unexpected, look closer on **Recognition**.

**Register a new employee**
1. **People** → **+ Add person**.
2. Enter their name, a clear photo, their employee number as **Code**, and tick **Staff**.
3. Ask them to walk past a camera, then look for their name in **Live view** or **Recognition**.

**Check whether someone came in today**
1. **Recognition**, with **Matched** selected and today's date → **Search**.
2. Find their name, then click 👁 for the camera, time and photos.

**Look into a stranger**
1. **Recognition** → set **Stranger** → **Search** → 👁 on the record. Note the **Track ID** and camera.
2. **Captures** → same date and **Device**, then type the **Track ID** to see all pictures of that pass.
3. If they should be known, add them on **People**.

**Add a camera**
1. Get the RTSP address, username and password from the installer.
2. **Devices** → **+ New device** → fill in → **Add device**.
3. After a minute, click **Refresh**: it should say **Online**. Check it in **Live view**.

**Set office hours (Mon–Fri, 9 to 5)**
1. **Time plans** → **Regular plans** → **+ New time plan** → name it *Office hours*.
2. Click **+** on Monday to Friday, then **Save draft**.

**Get an email when anyone is on camera D3 at night**
1. **Alarms** → **Recipients**: add each person and send a test email.
2. **Rules** → **+ New rule**: name *Night watch D3*, severity **Critical**.
3. Tick **IPCAM-D3**. Choose **Anyone** and tick **Body capture**.
4. **Set times**: all 7 days, **22:00** to **06:00**.
5. Tick the recipients → **Create rule**.

**Handle an alarm email**
1. Click the link in the email.
2. Check the snapshot, type your name and a note.
3. Click **Acknowledge**, then **Resolve** when dealt with, or **False alarm** if nothing was wrong.

**Find the busiest hours at the entrance last week**
1. **People counting** → **Cameras**: tick only the entrance camera.
2. **Period**: **Last 7 days**.
3. Look at **Busy times**: the darkest squares are the busiest hours.

---

## 14. Messages and what to do

| Message | What to do |
|---|---|
| *Incorrect username or password* | Use the password `admin` |
| *Missing or wrong API key* | Ask your administrator to check the API key settings |
| *B4H box unreachable* | Check the box is on and connected; wait if it's restarting |
| *The box took too long to answer* | Shorten the date range and try again |
| *Box error on …* | Try again. If it repeats, send the message to your administrator. |
| *Login to the box is paused…* | The portal's box password is wrong. Your administrator must fix it. |
| *A device named '…' already exists* | Choose another camera name |
| *photo is too large (max 5 MB)* / *photo must be an image* | Use a smaller JPEG or PNG |
| *…changing the groups failed* | Edit the person again and re-select the groups |
| *Stream unavailable* / *no video* | Click **Retry**. If it keeps failing, check the camera or tell your administrator. |
| *Too many live videos open* | Close some tiles or Live view tabs |
| *…isn't connected yet* | That feature isn't in the portal yet; use the box's own web page |
| *No records for these filters* / *No captures match these filters* | Widen the date range or clear filters |
| *Box clock unavailable* | Times still work. Tell your administrator if it continues. |
| *Dashboard numbers may be behind* | Check the box is on. The numbers catch up by themselves. |
| *Alarms need the portal database* / *People counting needs the portal database* | Ask your administrator |
| *Email isn't set up* | Ask your administrator to set up email |
| *Someone else changed this rule…* | Close the form and edit again |
| *A rule named '…' already exists* / *A recipient with the email … already exists* | Use another name, or edit the existing one |
| *…still being processed* (People counting) | Wait a few seconds |
| *This period has too many walk-pasts to compare…* | Pick a shorter period |
| *Page not found* | Click **Back to Dashboard** |

---

## 15. Questions

**Why are times on screen off by an hour or more?**
Your computer's time zone differs from the box's. Change your computer's time zone to match.

**A camera is Online but Live view is black. Why?**
Click **Reconnect**. If that fails, the camera's address or password may be wrong (check **Devices**), or video conversion isn't set up (tell your administrator).

**Why doesn't the camera filter show all records for that camera?**
On Recognition and Captures it only filters the loaded page. Use a shorter date range or a bigger page size.

**Someone I deleted still appears on Captures. Why?**
The box keeps old records. Recognition hides them; Captures shows everything.

**Can I undo a delete?**
No. Deleting records, people, cameras or plans changes the box permanently.

**I didn't get an alarm email. Why?**
Check that:
1. The rule is **On** and the camera is ticked.
2. The time was inside the rule's hours (box time).
3. You're a recipient and *Receives alarm emails* is ticked.
4. The rule wasn't in its quiet period.
5. The email isn't in your spam folder.

**Why did one email cover several people?**
During a rule's quiet period, new detections join the open alarm instead of sending more emails.

**Why does People counting say "≈" and show a range?**
Different people are worked out by comparing faces and clothing, which isn't perfect. See [Why "different people" is an estimate](#why-different-people-is-an-estimate).

**Is my data safe?**
Camera passwords are never shown. The sign-in is a demo, so only use the portal on your trusted internal network.

---

## 16. Glossary

| Term | Meaning |
|---|---|
| **Box** | The B4H device that analyses the cameras |
| **Face library** | The box's list of known people |
| **Recognition / match** | A face that matched someone in the face library |
| **Stranger** | A face that matched nobody in the library |
| **Capture** | A face or body picture the box saved |
| **Similarity** | How closely a face matches a library photo (0–100) |
| **Liveness** | How likely a face is a real person (0–100) |
| **Track / Track ID** | One person's continuous path past one camera, and its number |
| **Analysis task** | The job the box runs on a camera, e.g. face recognition |
| **RTSP address** | A camera's video address, starting with `rtsp://` |
| **Time plan** | A weekly schedule of when the box's rules are active |
| **Alarm** | A record that a rule matched someone, with a snapshot |
| **Rule** | Which cameras, who and when should raise an alarm |
| **Severity** | How serious an alarm is: Info, Warning or Critical |
| **Quiet period** | How long a rule waits before emailing again for the same camera |
| **Walk-past** | One person passing one camera once |
| **Different people** | How many separate people the walk-pasts were (an estimate) |
