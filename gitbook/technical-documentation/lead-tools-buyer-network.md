# Buyer Network

## What it does

An acquirer applies to join Wusool's buyer network. This replaced a Tally
form; it is the only tool built new rather than ported.

## How it works

1. The form collects name, organization, email, organization types, target
   geography, sectors, optional cheque size range, prior GCC acquisitions,
   and LinkedIn, plus consent.
2. `POST /buyer/apply` records it through the
   [write contract](lead-tools.md#the-write-contract) and confirms
   straight away.
3. In the background, Bedrock writes a short qualification note for the
   team. It is never shown to the applicant, and a failure never blocks the
   application.
4. Attio gets the organization, **one buyer role per sector ticked**, the
   person, and a Buy-side deal at Inbound. A repeat submission updates the
   roles it already has and adds new ones.

The option lists on the page are generated from the same sets the server
validates, and a test keeps them identical. A mistyped option would
otherwise record the lead and then fail to reach Attio.

## Status

Built and unit-tested, but not yet verified end to end against live Attio
and the database.

## Code

`server/app/modules/lead_magnets`: the `buyer_network` folders under
`domain` and `api`, and `static/buyers`.
