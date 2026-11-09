# Daily cloud run with GitHub (no laptop, no VPN, no Google key)

## 1. One-time GitHub setup (about 10 minutes)
1. Go to github.com and choose Sign up (free). Confirm your email.
2. Click the + at top right, then New repository. Name it `mobility-tracker`.
   Choose **Public** (the Google Sheet link in step 3 only works for public repos) and tick "Add a README file". Create it.
3. Unzip `mobility-tracker.zip` on your computer. In the repo, click Add file, then Upload files.
   Open the unzipped folder and drag **everything inside it** (including the hidden `.github` folder) into the page.
   If Windows hides `.github`, turn on View > Show > Hidden items in File Explorer first.
   Scroll down and click Commit changes.
4. Click the Actions tab. If it asks, click "I understand my workflows, enable them".
5. Click "Daily mobility price check" on the left, then Run workflow. After about 5-10 minutes it turns green.
   You should now see a `data` folder in the repo with `current.csv`, `history.csv` and `run_log.csv`.

## 2. Connect Google Sheets
In a new Google Sheet, cell A1 on a tab named `current`:
    =IMPORTDATA("https://raw.githubusercontent.com/YOUR-USERNAME/mobility-tracker/main/data/current.csv")
and on a tab named `history`:
    =IMPORTDATA("https://raw.githubusercontent.com/YOUR-USERNAME/mobility-tracker/main/data/history.csv")
Replace YOUR-USERNAME with your GitHub username. The sheet refreshes about hourly and shows the latest results.

## 3. Day to day
- It runs by itself every day. To run it now, Actions > Daily mobility price check > Run workflow.
- Check `data/run_log.csv` for any source marked FAILED. Failed sources keep their last good data.
- GitHub pauses scheduled jobs in a repo with no activity for 60 days. Daily result commits count as activity,
  but if it ever stops, the Actions tab has an Enable button.
