# Installing AlphaX Lab

Version 0.4.3

The install has failed twice on a correct repo, both times because the bench was
running an older commit than GitHub. These steps verify the deploy landed before
spending an install attempt on it.

---

## 1. Push

```bash
cd /path/to/alphax_lab
git add -A
git commit -m "AlphaX Lab v0.4.3"
git push origin main
```

Confirm on GitHub that the commit is on the branch the bench tracks. A push to a
branch the bench does not build looks like success and changes nothing.

## 2. Deploy on Frappe Cloud

**Pushing to GitHub does not update the server.** The bench directory is rebuilt
only by a deploy.

1. Open your Bench, go to the **Apps** tab.
2. Find AlphaX Lab. Check the commit hash shown against your latest commit.
3. If they differ, use **Update Available** to fetch the new commit.
4. Click **Deploy** and wait for it to finish.

If the Apps tab shows the right hash but the bench still serves old files, run a
full **Update All** rather than the incremental deploy. That is a stale build
artifact, and only a fresh build clears it.

## 3. Verify what is actually on disk

Before installing, from the bench:

```bash
python apps/alphax_lab/verify_tree.py
```

Expected:

```
OK: alphax_lab 0.4.3 structure verified
    patches.txt sections: pre_model_sync, post_model_sync
```

If the version is not 0.4.3, **stop**. The deploy did not land and installing
will reproduce the previous error. Go back to step 2.

If it reports a missing `[pre_model_sync]` header, the deploy did not land
either — that header has been present since 0.4.1.

## 4. Install

```bash
bench --site <site> install-app alphax_lab --force
```

`--force` is needed because the earlier failed attempts synced doctypes without
registering the app. The tables exist but `installed_apps` does not list it.

If the install reports a deadlock:

```
(1213, 'Deadlock found when trying to get lock; try restarting transaction')
```

That is lock contention, not corruption. Adding the unique `plasma_ref` index to
existing Sales Invoice and Delivery Note tables runs an ALTER TABLE that fights
live writes. Setup retries automatically and commits each step separately, so a
re-run resumes rather than restarts:

```bash
bench --site <site> set-maintenance-mode on
bench --site <site> migrate
bench --site <site> set-maintenance-mode off
```

## 5. Confirm the install

```bash
bench --site <site> execute alphax_lab.setup.install.status
```

Every doctype, custom field and the Lab workspace should read `yes`. Anything
marked `MISSING` is fixed by running `migrate` again.

In the desk UI, the **Lab** workspace should now appear with shortcuts to Lab
Test Consumption, Plasma Test Map, Lab Consumption Settings, and the three
reports.

## 6. Load demo data

```bash
bench --site <site> execute alphax_lab.demo.demo_data.setup
bench --site <site> execute alphax_lab.demo.demo_data.run_test
```

`run_test` posts a CBC plus LFT Delivery Note and prints the consumption Stock
Entry line by line. Two things to confirm in that output: both tests contributed
their own draw consumables, and the nearer-expiry reagent batch was picked.

Remove it all with:

```bash
bench --site <site> execute alphax_lab.demo.demo_data.teardown
```

---

## Housekeeping on neoaqua

Delete the `FG-BOT-1500` Plasma Test Map row before enabling the app. Mapping a
1.5L water bottle as a lab test would make every NeoAqua bottle sale attempt to
consume lab stock.
