# Add many profiles from a file

Use `/bulk-buyer` or `/bulk-seller` when you have a list of buyers or sellers in a spreadsheet. The bot checks the whole file first. Nothing is added until every row is valid and you confirm.

## Before you start

- Use the bot in a channel it's in, as with the other commands.
- Save your list as a CSV (choose **CSV UTF-8**) or as an Excel `.xlsx` file.
- A file can hold up to 1,000 rows.

## Add a list

1. Run `/bulk-buyer` or `/bulk-seller`.
2. Click **Download the template** in the form. It is a file with the column names in the first row.
3. Fill in one row per company.
4. Choose your file in the form and click **Check file**.
5. If the file is valid, the bot shows how many profiles it will add. Click **Add** to confirm.
6. The bot posts the result in the channel when it finishes.

## What each row needs

- **Organization name**
- **Domain**, which is the company's website, such as `acme.com`
- **Target vertical**, for buyers only

All other columns are optional. Leave a cell empty when you don't know the value.

## How to fill the columns

- For columns with a fixed list, such as Target vertical, use one of the allowed values. The bot lists them if a value doesn't match.
- To enter several values in one cell, separate them with `;`.
- Write money as a plain number in US dollars, such as `1500000`.
- Write dates as `2026-03-31`.
- Write yes or no questions as `Yes` or `No`.

## If the file has a problem

If any row is wrong, the bot adds nothing and lists every problem. Each one names the line and the column, for example `Line 7, Target vertical: not an allowed value`.

Fix those lines in your file and upload it again. If many lines are wrong, the bot also attaches the full list as a CSV.

If the bot says **Wrong template format**, your column names don't match the template. Download it again and copy your data into it.

## Companies already in the CRM

A company already in the CRM is skipped, and its record never changes. The bot counts these before you confirm.

- For buyers, a company counts when it has the same website and the same target vertical.
- A company with the same website but a new vertical gets a new buyer profile.
- For sellers, a company counts when it already has an active seller profile.

## If something goes wrong

- If the result lists failed rows, upload the file again. Rows already added are skipped.
- If you wait more than an hour before clicking **Add**, the check expires. Upload the file again.
- If the bot can't read your file, ask an admin to check the bot's file permission.
