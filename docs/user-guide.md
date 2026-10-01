# B4H Portal User Guide

This guide explains how to use the B4H Portal day to day: what each page is for, what you see on it, and step-by-step instructions for common tasks.

> **Who this is for:** security staff, receptionists, site managers and anyone else who uses the portal. You don't need any technical knowledge.
> **Setting the portal up** (installing, configuring, fixing the server) is covered in the [main README](../README.md).

---

## Contents

1. [What the portal does](#1-what-the-portal-does)
2. [Before you start](#2-before-you-start)
3. [Signing in and out](#3-signing-in-and-out)
4. [Finding your way around](#4-finding-your-way-around)
5. [Dashboard](#5-dashboard): today at a glance
6. [Live view](#6-live-view): watch cameras
7. [Recognition](#7-recognition): who was recognised, and strangers
8. [Captures](#8-captures): every face and body the cameras saw
9. [People](#9-people): the face library
10. [Devices](#10-devices): cameras
11. [Time plans](#11-time-plans): schedules
12. [Pages not available yet](#12-pages-not-available-yet)
13. [Step-by-step: common tasks](#13-step-by-step-common-tasks)
14. [Messages and what to do](#14-messages-and-what-to-do)
15. [Frequently asked questions](#15-frequently-asked-questions)
16. [Glossary](#16-glossary)

---

## 1. What the portal does

Your site has a **B4H analytics box** connected to its cameras. The box watches the video, recognises the faces of people it knows, and records everything it sees. The portal is the website you use to work with the box:

| You want to… | The portal lets you… |
|---|---|
| Know what's happening today | See totals, trends and problems on the **Dashboard** |
| Watch cameras | View up to 9 cameras live in **Live view** |
| Know who came in, and when | Search **Recognition** records |
| Spot unknown visitors | Find **strangers** (faces the box doesn't know) |
| Trace someone's movements | Browse **Captures** by camera, time and track |
| Register staff or visitors | Add people and photos to the **face library** |
| Manage cameras | Add, edit or remove cameras in **Devices** |
| Set working hours | Create schedules in **Time plans** |

**Key ideas in one minute**

- The **face library** is the box's list of known people. Each person has a reference photo.
- When a camera sees a face that matches someone in the library, the box saves a **recognition** (a "match").
- A face that matches nobody is a **stranger**.
- Every face or body the box picks out is also saved as a **capture**, whether it was recognised or not.
- **Similarity** (0–100) is how closely a face matches the library photo. **Liveness** (0–100) is how likely it is to be a real person rather than a photo held up to the camera.

---

## 2. Before you start

You need:

- A computer on the **same network** as the box (usually the office or site network).
- A modern browser: Chrome, Edge or Firefox.
- The portal's address. It is usually **http://localhost:3000** on the computer that runs it, or an address your administrator gives you.

> **Times:** the portal shows times using your computer's clock settings. Make sure your computer is set to the **same time zone as the box**, or times on screen will look shifted.

---

## 3. Signing in and out

### Sign in

1. Open the portal address in your browser. The **Sign in** page appears.
2. Type a **Username** (any name works for now) and the **Password** `admin`.
3. Click **Sign in**. The **Dashboard** opens.

If the password is wrong, you'll see *"Incorrect username or password."* Try again.

> **Note:** this is a demonstration sign-in. Individual user accounts aren't set up yet, so everyone uses the same password.

### Sign out

1. Click **Admin** at the top right of the screen.
2. Click **Sign out**. You return to the Sign in page.

Keyboard: press **Tab** until **Admin** is highlighted, press **Enter** to open the menu, and **Esc** to close it.

---

## 4. Finding your way around

```
┌──────────────┬─────────────────────────────────────────────────────────────┐
│ B4H Portal   │ [≡] [ Search… ]     Demo data  Devices 20/24  ● Live  EN|中  Admin ▾ │
│              ├─────────────────────────────────────────────────────────────┤
│ MONITOR      │                                                             │
│  Dashboard   │   Page title                                                │
│  Live view   │   Short description                                         │
│ EVENTS       │                                                             │
│  Alarms      │   ┌───────────────────────────────────────────────┐         │
│  Recognition │   │                                               │         │
│  Captures    │   │              page content                     │         │
│  People cnt. │   │                                               │         │
│ MANAGE       │   └───────────────────────────────────────────────┘         │
│  People      │                                                             │
│  Devices     │                                                             │
│  Time plans  │                                                             │
│  Settings    │                                                             │
└──────────────┴─────────────────────────────────────────────────────────────┘
```

### Sidebar (left)

| Group | Pages | Use it to… |
|---|---|---|
| **Monitor** | Dashboard, Live view | See what's happening now |
| **Events** | Alarms, Recognition, Captures, People counting | Look back at what the cameras detected |
| **Manage** | People, Devices, Time plans, Settings | Change what the box knows and does |

The page you're on is highlighted. To make more room, click the **collapse button** (left of the search box): the sidebar shrinks to icons. Hover an icon to see its name. Click the button again to expand it. The portal remembers your choice.

### Top bar

| Item | What it does |
|---|---|
| **Search box** | Takes you to the **People** page. It doesn't filter by what you typed yet. |
| **Demo data**, **Devices 20 / 24**, **Live** | Placeholder indicators that don't show real values yet. For real camera status, use the **Dashboard** or **Devices** page. |
| **EN \| 中** | Language choice. Pages are in English for now. |
| **Admin** | Sign out |

The red number next to **Alarms** in the sidebar is also a placeholder.

### Things that work the same everywhere

- **Esc** closes any open window or side panel (except while something is saving).
- **Deleting always asks you to confirm first.** Deletions change the box and **can't be undone**.
- **Errors appear in red** with an explanation. There is usually a **Try again**, **Refresh** or **Dismiss** button.
- **Pictures**: click a small picture in a table to open it full size in a new tab (on the Recognition page).
- **Refresh** buttons reload the latest data from the box.

---

## 5. Dashboard

**What it's for:** a one-screen summary of **today**: how many people were recognised, how many strangers, whether every camera is working, and what needs attention. Open it first each day.

**How it updates:** it refreshes by itself **every 45 seconds**. Click **Refresh** (top right) to update it now. If a refresh fails, the last good figures stay on screen with a red note: *"Showing last successful snapshot"*.

### What's on the page (top to bottom)

**Status line**: a green dot and *Box clock connected* means the box's clock was read. An amber dot and *Box clock unavailable* means it wasn't (see [FAQ](#15-frequently-asked-questions)). Today's date is shown alongside.

**Summary cards**

| Card | Shows |
|---|---|
| **Recognitions** | People matched to the face library today, and the change compared with yesterday (e.g. *+25% vs yesterday*, *New*, *No change*) |
| **Strangers** | Faces not in the library today, and their share of all face matches. **Red** when there are any, green when there are none. |
| **Cameras** | Online cameras / total cameras, and how many are streaming video. **Amber** if any are offline. |
| **Captures** | Face and body captures today, split into face and body |

**People flow**: counts the day's foot traffic without double counting:

| Figure | Meaning |
|---|---|
| **Tracked encounters** | How many separate times a person passed a camera (one per camera *track*, so someone walking past once counts once) |
| **Unique recognized people** | How many *different* library people were recognised |
| **Recognized encounters** | Passes by recognised people, and what share of face tracks they make up |
| **Stranger encounters** | Passes by strangers. The box can't tell whether two stranger passes were the same person, so this counts passes, not people. |

**Security activity by hour**: a bar for each hour of the day. The tallest bar is the **peak hour** (shown top right). Hover a bar to see its exact count.

**Signals worth checking**

| Signal | Meaning | When to act |
|---|---|---|
| **Average match score** | Average similarity of today's matches | A low average can mean poor lighting or old library photos |
| **Low-confidence matches** | Matches with similarity under 70% | Amber if any. Check these records; they might be wrong matches. |
| **Low-liveness matches** | Faces with liveness under 80% | Red if any. **Someone may have held up a photo or screen.** Investigate. |
| **Busiest camera** | Camera with the most recognition events | — |

**Camera readiness**: every camera with its analysis task and state:

| Dot | State | Meaning |
|---|---|---|
| 🟢 | **Ready** | Online and sending video |
| 🟡 | **Stream issue** | Online, but the box isn't receiving its video |
| 🔴 | **Offline** | The box can't reach the camera |

Click **Manage devices** to open the Devices page.

**Attention queue**: up to 5 problems, most serious first: a camera offline, a camera not streaming, a camera with no analysis task, or the box clock not readable. *No device issues detected* means all is well.

**Recent recognition activity**: the latest matches and strangers with camera, time and score. Click **View records** to open the Recognition page.

**Most recognized today**: the five people seen most often.

At the bottom: the time of the last refresh and the box's time zone.

> If the page says *"Trend metrics use the latest N recognition records; totals are complete"*, it was a very busy day. The totals are exact, but the charts and signals are based on a sample.

---

## 6. Live view

**What it's for:** watching up to 9 cameras at once, with the latest recognitions alongside.

### Layout of the page

| Area | What it shows |
|---|---|
| **Cameras** (left) | Every camera. 🟢 = online. Grey = offline (can't be selected). **on wall** = already showing in a tile. |
| **Video wall** (middle) | The video tiles. Choose **Layout 1**, **4** (the default) or **9**. |
| **Latest recognitions** (right) | Today's newest matches: face photo, name, camera, time and similarity. Updates every 5 seconds. Strangers aren't listed here. |

When the page opens, the online cameras fill the tiles automatically.

### Controls on each video tile

Hover the top of a tile to see its name, its analysis task, and these buttons:

| Button | What it does |
|---|---|
| **SD** / **HD** | Switches quality. **SD** = lighter, lower-resolution video (saves bandwidth). **HD** = full resolution. |
| ⟳ **Reconnect** | Restarts the video if it froze |
| ⤢ **Full screen** | Fills the screen with this camera. Press **Esc** to leave. |
| ✕ **Close** | Removes the camera from the tile |

Grid tiles use **SD** automatically; the 1-tile layout and full screen use **HD** automatically. You can override either with the SD/HD button.

### How to…

**Show a camera in a tile**
1. Click the tile you want to use. It gets a **blue outline**.
2. Click the camera in the **Cameras** list.
3. The next tile is selected automatically, so you can keep clicking cameras to fill the wall.

**Move a camera to another tile**: select the new tile, then click the camera again. It moves rather than appearing twice.

**Fix a frozen or black tile**: click ⟳ **Reconnect**. If the tile shows *"no video"*, click **Retry**.

### Good to know

- *"Stream unavailable. Check the camera, and that ffmpeg is installed on the backend."* means the camera can't be reached, or video conversion isn't set up on the portal's server. Tell your administrator.
- *"Too many live videos open"*: the portal allows about 16 videos at once across all users and tabs. Close tiles or other Live view tabs.
- Live video uses a lot of network bandwidth. Close the page when you're not watching.

---

## 7. Recognition

**What it's for:** finding out **who was recognised, where and when**, and finding **strangers**.

### Filters (top of the page)

| Filter | Options |
|---|---|
| **Capture device** | **All**, or one camera |
| **Recognition result** | **Matched** (person found in the face library) or **Stranger** |
| **From** / **To** | Date and time range. Default: today, 00:00 to 23:59. |

Click **Search** to load records with these filters. **Reset** puts the filters back to today, Matched and all cameras; click **Search** afterwards to reload.

> **Capture device** filters the records already loaded on the current page. It doesn't run a new search, so a page may show fewer than 10 rows. The footer then says *"showing N from <camera> on this page"*.

### The table

10 records per page. Use **Previous** / **Next** at the bottom; the footer shows the total and the page number.

| Column | Meaning |
|---|---|
| **Face** | The face the camera captured (click to open full size) |
| **Panoramic** | The whole camera frame |
| **Capture device** | Which camera |
| **Capture time** | When it happened |
| **Living fraction** | Liveness score (0–100). Low values can mean a photo or screen. |
| **Base image** | The person's photo in the face library |
| **Name** | The matched person (strangers have no library name) |
| **Group** | The person's groups, e.g. Staff |
| **Similarity** | How closely the face matched (0–100) |

### Record details

Click **👁 Details** on a row. A panel opens on the right with:

- The **name**, similarity, time and camera at the top.
- **Captured** and **Library photo** side by side. Switch the captured picture between **Face** and **Scene** (the whole frame).
- **Person**: the name and group tags.
- **Event**: the **Track ID** and **Living fraction**.
- **Face attributes**: age, gender, hat, glasses, mask, hairstyle and beard, as the box estimated them.
- **Other candidates**: other library people the face resembled, with their similarity.
- **Show raw data**: the box's original record, for technical support.

Close the panel with ✕, **Esc**, or by clicking outside it.

### Delete a record

1. Click the red 🗑 on the row.
2. A window asks *"Are you sure you want to delete this record?"* **Cancel** is selected by default, so pressing Enter is safe.
3. Click **Delete**. The record is removed from the box **permanently**.

### Good to know

- Records of people who have since been **removed from the face library** are hidden automatically.
- Very long date ranges can be slow. If you see *"The box took too long to answer"*, shorten the range.

---

## 8. Captures

**What it's for:** browsing **every face and body** the cameras picked out, recognised or not. Use it to trace someone's movements or check what a camera sees.

### Filters

Filters apply **as soon as you change them**; there's no Search button.

| Filter | Options |
|---|---|
| **From** / **To** | Dates (whole days). Default: today. |
| **Target type** | **All types**, **Face** or **Body** |
| **Device** | **All devices**, or one camera |
| **Track ID** | All or part of a track number, e.g. `5610081`. A track is one person's continuous path past one camera. |

**Reset** puts all filters back to today. **Refresh** reloads the data.

> **Device** and **Track ID** only filter the captures on the **current page**. A note appears to remind you. To search a whole day for one track, raise the page size to 30 and go through the pages.

### Views

Switch with the two icons on the right of the filter bar:

- **Grid** (default): one picture per capture, with a **Face** or **Body** badge, camera, time and track number.
- **List**: a table with Capture, Type, Device, Time, Track ID and a **Details** button.

At the bottom: *"Showing 1–10 of N"*, the page-size choice (**10**, **20** or **30 / page**) and page arrows.

### Capture details

Click a picture (grid) or **Details** (list). A window shows the full camera frame, the type, track number, camera and time, and the **attributes** the box detected. Attributes are shown as the box's **raw code numbers**; there's no legend for them yet.

Close with ✕, **Esc**, or by clicking outside the window.

---

## 9. People

**What it's for:** managing the **face library**, the people the box can recognise. Anyone not in it is reported as a **stranger**.

### The table

The top of the page shows how many people are registered. The table lists 10 people per page:

| Column | Meaning |
|---|---|
| **Person** | Photo, name and birthday (*No birthday recorded* if empty). If the photo can't load, the person's initial is shown. |
| **Code** | Optional code, e.g. an employee number |
| **Groups** | Group tags, or *Unassigned* |
| **Person ID** | The box's id for this person |
| **Actions** | **Details**, **Edit**, 🗑 delete |

Click **Refresh** to reload the list.

### Add a person

1. Click **+ Add person**.
2. Fill in:
   - **Name** (required)
   - **Reference photo** (required): a clear, front-facing photo of the face, at most 5 MB
   - **Code**, **Birthday**, **Groups** (tick one or more) and **Remarks** (all optional)
3. Click **Add person**. The person appears in the list and the box starts recognising them.

### View a person

Click **Details** to see their photo, person ID, code, birthday, groups and remarks. Click **Edit person** to change them.

### Edit a person

1. Click **✎ Edit** on the row.
2. Change any fields.
   - **To keep the current photo, leave Reference photo empty.** To replace it, choose a new file.
   - **Groups:** the ticked groups replace the person's groups. If you untick *every* group, the groups are left unchanged. To remove someone from all groups, use the box's own web interface.
3. Click **Save changes**.

### Delete a person

1. Click the red 🗑 on the row.
2. Confirm in the browser's pop-up (*"Delete <name> from the face library?"*).

The person is removed from the box. Their past recognition records are hidden from the Recognition page.

### Tips for good recognition

- Use a **sharp, well-lit, front-facing** photo with **only one face** in it.
- Avoid sunglasses, hats and heavy shadows.
- If the box rejects a photo, try a clearer one or crop closer to the face.
- Put people in **groups** (e.g. Staff, Contractors, Visitors) so they're easy to tell apart in records.

---

## 10. Devices

**What it's for:** managing the **cameras connected to the box**: see which are online, and add, edit or remove them.

### At the top

- Counts of **Cameras**, **Online** and **Offline**.
- **Filters** that apply as you type: **Device name**, **Status** (All / Online / Offline) and **Address** (e.g. an IP address). **Reset** appears while a filter is active.
- **+ New device**, **Refresh**, and the **grid** / **list** view icons.

### The list (default view)

| Column | Meaning |
|---|---|
| **Device** | Name and device number (e.g. `#2`) |
| **Type** | Video or Picture |
| **Protocol** | RTSP (or GB28181) |
| **Host** | The camera's IP address and port |
| **Stream** | The stream path on the camera |
| **Status** | **Online** or **Offline**. Hover *Offline* to see the box's status code (useful for support). |

The **grid view** shows the same as cards, plus a **Streaming** / **Not streaming** badge on online cameras.

Camera passwords are **never shown**. Addresses appear as `user:****@…`.

### Add a camera

1. Click **+ New device**.
2. Enter a **Device name** (must be unique, e.g. *Main entrance*).
3. Choose **Device type: Video** and **Protocol: RTSP**.
4. Enter the **RTSP address**, e.g. `rtsp://192.168.90.24:554/ISAPI/Streaming/channels/201`. It must start with `rtsp://`. Your camera installer or the camera's manual gives this address.
5. Enter the camera's **Username** and **Password**. Click the 👁 icon to check what you typed.
6. Click **Add device**. A green message confirms it, e.g. *Added "Main entrance" as device #4.* The device number is chosen automatically.

> **Picture** devices and **GB28181** cameras can be selected but not saved yet. The window explains this, and **Add device** stays disabled. Use the box's own web interface for these.

### Edit a camera

1. Click **✎ Edit**.
2. Change the name, RTSP address or username.
3. **Leave Password empty to keep the current password.** Type a new one only if it has changed.
4. Click **Save changes**.

### Remove a camera

1. Click the red 🗑.
2. Confirm with **Delete**. The box stops analysing that camera. This can't be undone.

### Good to know

- **Online** but **Not streaming** (grid view) means the camera answers but the box isn't getting video. Check the stream path, username and password.
- You don't need to put the username and password inside the RTSP address; the separate fields are enough.

---

## 11. Time plans

**What it's for:** creating **schedules** that say *when* the box's rules are active, for example office hours only, or 24/7.

- **Regular plans** repeat every week.
- **Festival plans** are for holidays and special days.

> **All times are in the box's time zone**, not your computer's.

### Layout of the page

| Area | What it shows |
|---|---|
| **Top bar** | **Regular plans** / **Festival plans** tabs; the clock (*Box clock* with a green dot, or *Portal clock* with an amber dot if the box clock couldn't be read); a ⟳ refresh button |
| **Plan list** (left) | **Find a plan** search, **+ New time plan**, and the plans. Each plan is labelled *Box plan*, *Default plan* (green dot) or *Local draft*. |
| **Editor** (middle) | The selected plan: its name, a weekly timeline, and the **Daily windows** for each day |
| **Side panel** (right) | The box clock and time zone; a **Plan summary** (type, number of plans, active days out of 7) |

The weekly timeline shows each day from **Monday to Sunday** as a bar from 00:00 to 24:00, with blue blocks where the plan is active.

### Create a plan

1. Choose the **Regular plans** or **Festival plans** tab.
2. Click **+ New time plan**. A *Local draft* appears.
3. Click the plan's name at the top of the editor and type a new one, e.g. *Office hours*.
4. For each day the plan should be active, click **+** (or **Add a window**). A window from **09:00 to 17:00** is added.
5. Change the start and end times as needed. For a split day (e.g. 08:00–12:00 and 13:00–17:00), add a second window.
6. Leave a day with no windows to keep it **off**.
7. Click **Save draft**. The plan is created on the box, and a message confirms it.

> A new plan is only kept **in your browser** until you click **Save draft**. Nobody else can see it, and the box doesn't use it.

### Edit a plan

1. Select the plan in the list.
2. Change the name or the windows. To remove a window, click the 🗑 next to it.
3. Click **Save to box**.

> Changes you haven't saved are kept **in your browser** and are not on the box yet. If you leave the page and come back, your unsaved changes are still shown. Click **Save to box** to apply them.

### Delete a plan

1. Select the plan.
2. Click the 🗑 button next to the Save button at the top of the editor.
3. Confirm in the browser's pop-up. For a box plan it asks *Delete "…" from the box?*, which **can't be undone**. For a local draft it asks *Discard the local draft "…"?*, which only removes it from your browser.

---

## 12. Pages not available yet

These pages are in the sidebar but show a placeholder for now:

| Page | Planned purpose |
|---|---|
| **Alarms** | A list of alarms raised by the box's rules |
| **People counting** | Counts of people entering and leaving over time |
| **Settings** | Portal and box settings |

---

## 13. Step-by-step: common tasks

### Daily check (2 minutes)

1. Open the **Dashboard**.
2. Look at the **Attention queue**. Any offline camera? Tell your administrator or check the camera.
3. Look at **Strangers** and **Low-liveness matches**. If either is unexpected, open **Recognition** to look closer.
4. Glance at **Camera readiness**: every camera should be 🟢 **Ready**.

### Register a new employee

1. Take a clear, front-facing photo of their face.
2. Go to **People** → **+ Add person**.
3. Enter their **Name**, choose the **photo**, optionally a **Code** (employee number), and tick the **Staff** group.
4. Click **Add person**.
5. To check it works, ask them to walk past a camera, then look for their name in **Live view → Latest recognitions** or on the **Recognition** page.

### Find out whether someone came in today

1. Go to **Recognition**.
2. Leave **Recognition result** on **Matched** and the dates on today.
3. Click **Search**, then look for their name. Use **Previous / Next** to page through.
4. Click **👁 Details** to see the camera, time and photos.

### Look into a stranger

1. Go to **Recognition**, set **Recognition result** to **Stranger**, and click **Search**.
2. Click **👁 Details** on the record. Note the **Track ID** and camera.
3. Go to **Captures**, set the same date, choose the **Device**, and type the track number in **Track ID** to see the other pictures of that pass.
4. If the person should be known, add them on the **People** page.

### Add a new camera

1. Get the camera's **RTSP address**, **username** and **password** from the installer.
2. Go to **Devices** → **+ New device**, choose **Video** and **RTSP**, and fill in the details.
3. Click **Add device**.
4. Click **Refresh** after a minute. The camera should show **Online**. Open **Live view** to check the picture.

### Set office hours (Monday to Friday, 9 to 5)

1. Go to **Time plans** → **Regular plans** → **+ New time plan**.
2. Rename it *Office hours*.
3. Click **+** on Monday to Friday. Each gets a 09:00–17:00 window.
4. Click **Save draft**.

---

## 14. Messages and what to do

| Message | What it means | What to do |
|---|---|---|
| *Incorrect username or password.* | Wrong sign-in password | Use the password `admin` |
| *Missing or wrong API key* | The portal isn't allowed to talk to its server | Ask your administrator to check the API key settings |
| *B4H box unreachable* | The portal's server can't reach the box | Check the box is powered on and connected; wait if it's restarting |
| *The box took too long to answer* | The search was too big, or the box is busy | Shorten the date range and try again |
| *Box error on …* | The box refused the request | Try again. If it repeats, report the full message to your administrator. |
| *Login to the box is paused…* | The portal's box password is wrong | Your administrator must fix the password and restart the portal's server |
| *A device named '…' already exists* | Camera names must be unique | Choose another name |
| *photo is too large (max 5 MB)* | The face photo file is too big | Use a smaller photo |
| *photo must be an image* | The chosen file isn't a picture | Choose a JPEG or PNG file |
| *Person details were saved, but changing the groups failed* | The name/photo were saved but not the groups | Edit the person again and re-select the groups |
| *Stream unavailable…* / *no video* | Live video couldn't start | Click **Retry**; if it keeps failing, check the camera or tell your administrator |
| *Too many live videos open* | Too many videos are playing at once | Close tiles or other Live view tabs |
| *…isn't connected yet* (button disabled) | That feature isn't finished in the portal | Use the box's own web interface for now |
| *No records for these filters.* / *No captures match these filters.* | Nothing matched | Widen the date range or clear filters |
| *Box clock unavailable* / *Portal clock* | The box's clock couldn't be read | Times still work. Tell your administrator if it persists. |
| *Page not found* | The address doesn't exist | Click **Back to Dashboard** |

---

## 15. Frequently asked questions

**Why does someone I deleted from People still show up in old records?**
The box keeps old records after a person is deleted. The portal hides them on the Recognition page; you might still see them on the Captures page, which shows every capture.

**Why are the times on screen an hour (or more) off?**
Your computer's time zone differs from the box's. Set your computer to the box's time zone.

**Why does the Dashboard say "Box clock unavailable"?**
Some box models don't report their clock. The figures are still correct; the portal just can't show the box's own time.

**A camera is "Online" but the Live view is black. Why?**
The box can reach the camera, but its video couldn't be converted for the browser. Click **Reconnect**. If that fails, the camera's stream address or password may be wrong (check **Devices**), or video conversion isn't set up on the server (tell your administrator).

**Why doesn't the camera filter on Recognition or Captures show all records for that camera?**
These filters only work on the page that's already loaded. Use a narrower date range, or (on Captures) a larger page size, and page through.

**Can I undo a delete?**
No. Deleting records, people, cameras or time plans changes the box permanently.

**Is my data safe?**
Camera passwords are never shown in the portal. The sign-in is currently a demonstration, so only use the portal on your trusted internal network.

---

## 16. Glossary

| Term | Meaning |
|---|---|
| **Box** | The B4H analytics device that watches the cameras |
| **Face library** | The list of known people the box can recognise |
| **Recognition / match** | A face that matched someone in the face library |
| **Stranger** | A face that matched nobody in the face library |
| **Capture** | A face or body picture the box saved, recognised or not |
| **Similarity** | How closely a face matches a library photo (0–100) |
| **Liveness / living fraction** | How likely a face is a real, live person (0–100) |
| **Track / Track ID** | One person's continuous path past one camera, and its number |
| **Panoramic / Scene** | The whole camera picture the face or body was taken from |
| **SD / HD** | Lower-quality (lighter) / full-quality video |
| **Analysis task** | The job the box runs on a camera, e.g. face recognition |
| **Time plan** | A weekly schedule of when the box's rules are active |
| **RTSP address** | The camera's video address, starting with `rtsp://` |
