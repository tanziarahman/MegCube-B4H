# B4H Portal: User Guide

How to use each page of the B4H Portal: what it's for, what you see, and how to do common tasks.

For installing and running the portal, see the [main README](../README.md). For the box endpoints behind each page, see [box-api.md](box-api.md#14-portal-pages-and-the-box-calls-behind-them).

---

## Contents

1. [Signing in](#1-signing-in)
2. [Finding your way around](#2-finding-your-way-around)
3. [Dashboard](#3-dashboard): today at a glance
4. [Live view](#4-live-view): watch cameras
5. [Recognition](#5-recognition): who was recognised, and strangers
6. [Captures](#6-captures): every face and body the cameras picked up
7. [People](#7-people): the face library
8. [Devices](#8-devices): add and manage cameras
9. [Time plans](#9-time-plans): schedules for when rules run
10. [Pages not available yet](#10-pages-not-available-yet)
11. [Messages you may see](#11-messages-you-may-see)
12. [Quick reference: which page do I need?](#12-quick-reference-which-page-do-i-need)

---

## 1. Signing in

1. Open the portal in your browser (usually **http://localhost:3000**).
2. Enter any **username** and the password **`admin`**, then click **Sign in**.
3. A wrong password shows *"Incorrect username or password."* and keeps you on the sign-in page.

> This is a demo sign-in. Real user accounts aren't connected yet.

To sign out, click your name (**Admin**) at the top right and choose **Sign out**. The menu also works with the keyboard: Tab to it, press Enter to open it, and Esc to close it.

---

## 2. Finding your way around

**Sidebar (left)**. The pages are grouped by purpose:

| Group | Pages | Use it to… |
|---|---|---|
| **Monitor** | Dashboard, Live view | See what's happening now |
| **Events** | Alarms, Recognition, Captures, People counting | Look back at what the cameras detected |
| **Manage** | People, Devices, Time plans, Settings | Change what the box knows and does |

The button at the top of the page, left of the search box, collapses or expands the sidebar.

**Top bar**:

| Item | What it does |
|---|---|
| Search box | Takes you to the **People** page. Filtering by the search text isn't built yet. |
| **Demo data**, **Devices 20 / 24**, **Live** | Placeholder indicators, not yet live. Use the **Dashboard** or **Devices** page for real camera status. |
| **EN \| 中** | Language choice (remembered in your browser). The pages are in English for now. |
| **Admin** menu | Sign out |

**Everywhere in the portal**:
- **Esc** closes any open dialog or side panel (except while it is saving).
- Deleting anything asks for confirmation first, and deletions on the box **can't be undone**.
- If something fails, a red message explains why. There is usually a **Try again** or **Refresh** button.

---

## 3. Dashboard

**What it's for:** a one-screen summary of **today**: how many people were recognised, strangers, camera health, and what needs attention. Open it first each day.

It refreshes itself **every 45 seconds**. Click **Refresh** (top right) to update it now. If a refresh fails, the last good data stays on screen with a red note.

**What you see, top to bottom:**

| Section | Shows |
|---|---|
| Status line | Whether the **box clock** could be read (green) or not (amber), today's date, and the refresh interval |
| **Recognitions** | People matched to the face library today, and the change vs yesterday |
| **Strangers** | Faces not in the library today, and their share of all face matches. Red if there are any. |
| **Cameras** | Online / total cameras, and how many are streaming. Amber if any are offline. |
| **Captures** | Face and body captures today |
| **People flow** | *Tracked encounters* (one per camera track, so the same person walking past once counts once), *Unique recognised people*, *Recognised encounters*, *Stranger encounters*. Two stranger tracks can't be proven to be the same person, so strangers are counted per track. |
| **Security activity by hour** | Bar chart of events per hour, with the **peak hour**. Hover a bar for its count. |
| **Signals worth checking** | *Average match score*; *Low-confidence matches* (score under 70%); *Low-liveness matches* (liveness under 80%, which may be a photo or screen held up to the camera); *Busiest camera* |
| **Camera readiness** | Each camera with its task and state: 🟢 **Ready**, 🟡 **Stream issue** (online but not streaming), 🔴 **Offline**. **Manage devices** opens the Devices page. |
| **Attention queue** | Up to 5 problems: offline cameras, cameras not streaming, cameras with no analysis task, or the box clock not readable |
| **Recent recognition activity** | Latest matches and strangers with camera, time and score. **View records** opens the Recognition page. |
| **Most recognised today** | People seen most often today |

**Tip:** check *Low-liveness matches*. A high number can mean someone is trying to fool a camera with a photo.

---

## 4. Live view

**What it's for:** watching cameras live, up to 9 at once, with the latest recognitions beside the video.

**Layout of the page:**
- **Cameras** list (left): 🟢 online, grey = offline (can't be selected). **on wall** marks cameras already showing.
- **Video wall** (middle): choose **Layout 1, 4 or 9** tiles.
- **Latest recognitions** (right): today's newest matches with face photo, name, camera, time and similarity. It updates every 5 seconds.

When the page opens, the online cameras fill the tiles automatically.

**How to…**

| Task | Steps |
|---|---|
| Put a camera in a tile | Click the tile (it gets a blue outline), then click the camera in the list. The next tile is selected automatically, so you can click cameras one after another. |
| Move a camera | Select the new tile and click the camera again. It moves rather than appearing twice. |
| Remove a camera | Click **✕** on the tile |
| Watch full screen | Click **⤢** on the tile. Press Esc to leave. |
| Sharper / lighter video | Click **SD / HD**. Grid tiles use **SD** (light sub-stream) to save bandwidth. The 1-tile layout and full screen use **HD** automatically. |
| Video froze or dropped | Click **⟳ Reconnect** on the tile. If it shows *"no video"*, click **Retry**. |

**Notes**
- A tile that says *"Stream unavailable. Check the camera, and that ffmpeg is installed on the backend."* means the camera is unreachable or video conversion isn't set up on the backend computer. Tell whoever runs the backend.
- *"Too many live videos open"*: the backend limits how many videos run at once (16 by default). Close tiles or other browser tabs showing Live view.
- Live video uses network bandwidth. Close the page when you're not watching.

---

## 5. Recognition

**What it's for:** looking up **who was recognised, where and when**, and finding **strangers** (faces not in the face library).

**Filters** (top):

| Filter | Options |
|---|---|
| **Capture device** | All cameras, or one camera |
| **Result** | **Matched** (person found in the face library) or **Stranger** |
| **From / To** | Date and time range (default: today) |

Click **Search** to apply the filters. **Reset** goes back to today, Matched, all cameras.

**The table** (10 records per page, with **Previous / Next** buttons) shows the face picture, the library (base) image, a panoramic picture, the name, the group, similarity, liveness ("living fraction"), the camera and the time.

**How to…**

| Task | Steps |
|---|---|
| See full details | Click **👁 Details** on a row. A side panel shows the person, the event (camera, time, track ID), face attributes, the library photo, other candidate matches, and **Show raw data** for the box's original record. Esc closes it. |
| Delete a record | Click **🗑** on the row, then **Delete** in the confirmation. It is removed from the box **permanently**. |
| Find today's strangers | Result = **Stranger**, then **Search** |

**Notes**
- **Similarity** = how closely the face matches the library photo. **Living fraction** = how likely the face is a real, live person rather than a photo.
- Records for people who have since been **deleted from the face library** are hidden automatically.
- The camera filter applies to the records that were loaded, not a new search on the box.
- Very long date ranges can be slow. If you see *"The box took too long to answer"*, shorten the range.

---

## 6. Captures

**What it's for:** browsing **every face and body** the cameras captured, whether recognised or not. Use it to trace someone's movements or check what a camera sees.

**Filters:**

| Filter | Options |
|---|---|
| **Target type** | All types, **Face**, **Body** |
| **Device** | All devices, or one camera |
| **From / To** | Date and time range |
| **Track ID** | A track number, e.g. `5610081` (one person's continuous path through one camera) |

**Reset** clears the filters and **⟳ Refresh** reloads. Switch between **grid** (pictures) and **list** (table) with the icons on the right. Choose **10, 20 or 30 per page** at the bottom.

Click a capture to open its details: the cropped target, the panoramic image, camera, time, track ID and the attributes the box detected.

**Notes**
- The **Device** and **Track ID** filters only narrow the records **on the current page**. A note on the page reminds you of this.
- Attributes are shown with the box's own raw codes. There is no legend for them yet.

---

## 7. People

**What it's for:** managing the **face library**, the list of known people the box recognises. Anyone not in it shows up as a **Stranger**.

**The table** shows each person's photo, name, person ID, code, groups and birthday, 10 per page. **⟳ Refresh** reloads it.

**How to…**

| Task | Steps |
|---|---|
| Add a person | Click **+ Add person**. Enter the **Name** (required) and choose a **Reference photo** (required: a clear, front-facing face, up to 5 MB). Optionally fill in Code, Birthday, Groups and Remarks. Click **Add person**. |
| View a profile | Click **Details** on the row. Esc closes it. |
| Edit a person | Click **✎ Edit** and change the fields. **Leave the photo empty to keep the current photo**, or choose a new one to replace it. Click **Save changes**. |
| Delete a person | Click **🗑**, then confirm. The person is removed from the box, and their old recognition records are hidden. |

**Tips for good recognition**
- Use a well-lit, sharp, front-facing photo, with only one face in it.
- Put people in **groups** (e.g. Staff, Visitors) so rules and reports can treat them differently.
- If a photo is rejected by the box, try a clearer one or crop closer to the face.

---

## 8. Devices

**What it's for:** managing the **cameras connected to the box**: see which are online, and add, edit or remove them.

**At the top:** counts of cameras, online and offline. **Filters** by **Device name**, **Status** (All / Online / Offline) and **Address** (IP). **Reset** clears them. Switch **list / grid** view with the icons. **⟳ Refresh** reloads.

**The table** shows each camera's name and ID, type, protocol, host, stream path, **Stream** (Streaming / Not streaming) and **Status** (Online / Offline; hover for the box's status code).

**How to…**

| Task | Steps |
|---|---|
| Add a camera | Click **+ New device**. Enter the **Device name** and choose **Device type: Video** and **Protocol: RTSP**. Enter the **RTSP address** (e.g. `rtsp://192.168.90.24:554/ISAPI/Streaming/channels/201`), then the camera's **Username** and **Password**. Click **Add device**. The ID is assigned automatically. |
| Edit a camera | Click **✎ Edit**, change the name, address or username, and click **Save changes**. **Leave Password empty to keep the current password.** |
| Remove a camera | Click **🗑**, then **Delete**. The box stops analysing that camera. This can't be undone. |

**Notes**
- The RTSP address must start with `rtsp://`. You don't need to put the username and password in the address; the separate fields are enough.
- Camera passwords are **never shown** in the portal. Addresses appear as `user:****@…`.
- Device names must be unique.
- **Picture** devices and **GB28181** cameras can be selected but not saved yet. The dialog says so.
- A camera that's **Online** but **Not streaming** is reachable but not sending video. Check its stream path and credentials.

---

## 9. Time plans

**What it's for:** creating **schedules** that say *when* the box's rules are active, for example office hours only, or 24/7.

- **Regular plans** repeat every week.
- **Festival plans** are for special days and holidays.

**Layout:** switch between **Regular plans** and **Festival plans** at the top. The box's current clock and time zone are shown alongside. The left column lists the plans (**Find a plan** searches them; the default plan has a green dot). The right side is the editor.

**How to…**

| Task | Steps |
|---|---|
| Create a plan | Click **+ New time plan**. Name it, then for each day click **+** to add a time window (it starts at 09:00–17:00) and adjust the start and end times. Add more than one window for a split day (e.g. 08:00–12:00 and 13:00–17:00). A day with no windows is **off**. Click **Save to box**. |
| Edit a plan | Select it, change the windows or name, and click **Save to box** |
| Remove a time window | Click **✕** next to the window |
| Delete a plan | Select it and click the **🗑** button, then confirm. This can't be undone. |

**Drafts:** a new plan is first a **Local draft**, saved only in **your browser**. It isn't on the box until you click **Save to box**. Deleting a local draft removes it only from your browser.

**Notes**
- **Times use the box's (recorder's) time zone**, not your computer's.
- If the box clock can't be read, the page shows *Portal clock* instead. Check with whoever manages the box.

---

## 10. Pages not available yet

These pages are in the sidebar but show a placeholder for now:

| Page | Planned purpose |
|---|---|
| **Alarms** | A list of alarms raised by the box's rules |
| **People counting** | Counts of people entering and leaving over time |
| **Settings** | Portal and box settings |

---

## 11. Messages you may see

| Message | What it means | What to do |
|---|---|---|
| *Missing or wrong API key* | The portal isn't allowed to talk to its backend | Ask the administrator to check the API key settings |
| *B4H box unreachable* | The backend can't reach the box | Check the box is powered on and on the network, and wait if it's rebooting |
| *The box took too long to answer* | The request was too big or the box is busy | Shorten the date range, then try again |
| *Box error on …* | The box refused the request | Read the message. Try again, or report it with the text shown. |
| *A device named '…' already exists* | Device names must be unique | Choose another name |
| *photo is too large* | The face photo is over the size limit (5 MB) | Use a smaller image |
| *…isn't connected yet* (button disabled) | That feature isn't finished in the portal | Use the box's own web UI for now |
| *No records for these filters* | Nothing matched | Widen the date range or clear the filters |

---

## 12. Quick reference: which page do I need?

| I want to… | Go to |
|---|---|
| See how today is going | **Dashboard** |
| Watch a camera now | **Live view** |
| Find out if/when a specific person was seen | **Recognition** (Result: Matched, pick the date) |
| See unknown faces | **Recognition** (Result: Stranger) or **Dashboard** → Strangers |
| Trace where someone went | **Captures** (filter by Track ID or camera and time) |
| Register a new employee or visitor | **People** → Add person |
| Change someone's photo | **People** → Edit |
| Check which cameras are offline | **Dashboard** → Camera readiness, or **Devices** (Status: Offline) |
| Add or fix a camera | **Devices** |
| Limit when rules run (e.g. office hours) | **Time plans** |
