# Design notes

Why this is built the way it is. Written after five months of daily runs, so these
are decisions that held up, not guesses.

## The problem

Careers portals show you every open role. They don't show you what appeared since
you last looked. For a student hunting Praktikum and Werkstudent positions at one
employer in one city, that means opening the same page every morning, scanning a
list you mostly recognise, and hoping you notice the two new rows. Good postings
fill up in days, so checking weekly is too slow and checking daily by hand is
tedious enough that you stop.

I wanted the opposite shape: nothing to open, one mail a day, and if there's
nothing new, it says so.

## Why the SmartRecruiters public API instead of scraping

Bosch runs its careers site on SmartRecruiters, and SmartRecruiters exposes every
customer's postings through a documented public API:

```
GET https://api.smartrecruiters.com/v1/companies/{company}/postings
```

No key, no OAuth, no account. Rate limit is 10 requests per second; this script
makes one. The response is JSON with the fields the digest needs already in it —
title, release date, experience level, posting id.

That removes the entire failure mode a scraper lives with. No HTML parsing, no
selectors that silently return nothing after a redesign, no cookie banner, no
headless browser in CI. It also removes the ambiguity about whether I'm allowed
to do this — a public, documented, unauthenticated endpoint is meant to be read.

The one thing I gave up: the list endpoint returns an empty `department` field.
Filling it would mean one detail request per posting. Not worth it for a column
in a table, so the digest doesn't show department.

## Why a 72-hour lookback instead of tracking which postings I've seen

The obvious design is a seen-set: store the ids you've already mailed, diff each
run, mail the difference. It's also the design that needs somewhere to put the
state. On GitHub Actions that means committing a file back to the repo, caching
it, or standing up a database — each of which adds a way for the job to break
that has nothing to do with jobs.

A time window needs no state at all. Every run is a pure function of the API
response and the clock. The cost is that a posting released 3 days ago shows up
in three consecutive mails.

That turned out to be a feature. The duplicates are the reason I trust the mail:
if I skim past something on Monday, it's still there Tuesday. And because the
window (72h) is wider than the interval (24h), a failed run isn't a hole — the
next day's mail still covers everything the missed one would have. A seen-set
would have made a missed run permanently invisible.

If the window ever needs to be tighter than the schedule, the tradeoff flips and
state-tracking wins. At 72h against a daily cron it doesn't.

## Why Gmail SMTP instead of SendGrid or SES

The recipient is me. One address, one message a day.

SendGrid and SES are built for sending to other people: they want a verified
domain, they want you out of the sandbox, they have deliverability dashboards and
bounce webhooks and a signup flow. All of that exists to solve problems that only
appear when strangers receive your mail.

Gmail SMTP is in the Python standard library — `smtplib`, no dependency — and
mail from my own account to my own inbox never lands in spam. Setup is a 2FA App
Password and two Actions secrets.

The limitation is real and worth stating: this does not scale past personal use.
Gmail caps outbound volume, and sending to a list from a personal account is how
you get the account flagged. If this ever fanned out to multiple recipients, the
transport is the first thing to replace. For a digest addressed to its own author,
it's the smallest thing that works.

## Why GitHub Actions instead of a VPS cron

The script runs for about ten seconds a day. A VPS to hold it would be a machine
I have to patch, a cron I have to notice has stopped, and a bill.

Actions gives the schedule, the runtime, and the secret storage in one place, free
for this workload, and — the part that mattered most — a run log per day. When
something failed, the traceback was already sitting in the Actions tab next to the
run that produced it. I never had to SSH anywhere to find out why a mail didn't
arrive.

Two things to know about the scheduler: cron times are UTC, not local, so
`0 5 * * *` is 07:00 CEST in summer and 06:00 CET in winter — the mail moves an
hour with daylight saving and I decided that was fine. And GitHub queues scheduled
runs rather than firing them on the second, so 05:00 in practice means some
minutes after. Neither matters for a daily digest; both would matter if this were
time-critical.

## Why an empty digest still sends a mail

A run that finds nothing sends "no new jobs" rather than staying quiet. Silence is
ambiguous — a quiet inbox looks identical whether there were no postings or the
workflow has been broken for a week. The empty mail is a heartbeat, and it costs
one line of HTML.

## Why the company and city are hardcoded

`CONFIG` at the top of `main.py` holds the company slug, city, country, window,
experience levels and keywords. They're constants in the file, not environment
variables.

Env vars would buy the ability to change the target without editing code — which
matters when the same code runs for several targets or several people. Here it
runs for one target, and putting the values in Actions secrets or repo variables
would have moved the configuration somewhere I can't see it in a diff, can't
review in a pull request, and can't tell what it was six months ago.

A fork changes six lines in one dict and gets the same tool pointed somewhere
else. That's the right amount of ceremony for this.

## What isn't handled

- **Malformed dates** are skipped rather than crashing the run, so one bad posting
  can't cost the whole digest. In five months the API never sent one.
- **Transient API or SMTP failures** have no retry. The run fails loudly in
  Actions and the next day's run — with its 72-hour window — covers what was
  missed. Retry logic would be code that exists to handle a case the schedule
  already handles.
- **Pagination** isn't implemented. One city's postings for one employer sit well
  under the 100-item limit (Reutlingen ran around 57 total). A larger location
  would need to page through `offset`.
