"""Locally-scoped Pydantic models for the three HarvestAPI actors' dataset
items (`linkedin-profile-scraper`, `linkedin-profile-posts`,
`linkedin-company`) and their run inputs — never exported as this module's
public schema. Only the subset `linkedin.py`/`company.py` map is declared;
every field is optional since a profile or page may omit any of them.

Field names follow each actor's published output example on its Apify page
(camelCase kept verbatim). The company and posts shapes were verified
against a live run on 2026-10-19 (the Lokam.ai page). The profile scraper has
not been run yet, so `ApifyProfileItem` is still unverified. The fixtures
under `tests/fixtures/apify/` are trimmed to the declared fields with
placeholder values.
"""

from pydantic import BaseModel, Field

PROFILE_ACTOR = "harvestapi~linkedin-profile-scraper"
POSTS_ACTOR = "harvestapi~linkedin-profile-posts"
COMPANY_ACTOR = "harvestapi~linkedin-company"


class ProfileScraperInput(BaseModel):
    profileScraperMode: str = "Profile details no email ($4 per 1k)"
    queries: list[str]


class ProfilePostsInput(BaseModel):
    targetUrls: list[str]
    maxPosts: int
    postedLimit: str


class CompanyInput(BaseModel):
    companies: list[str]


class ApifyDate(BaseModel):
    # "Present" for an open-ended position.
    text: str | None = None


class ApifyParsedLocation(BaseModel):
    # `country` is the short common name ("United States"); `countryFull` the
    # formal one ("United States of America").
    country: str | None = None
    countryFull: str | None = None


class ApifyProfileLocation(BaseModel):
    linkedinText: str | None = None


class ApifyCurrentPosition(BaseModel):
    companyName: str | None = None
    position: str | None = None


class ApifyExperience(BaseModel):
    position: str | None = None
    companyName: str | None = None
    endDate: ApifyDate | None = None


class ApifyProfileItem(BaseModel):
    publicIdentifier: str | None = None
    linkedinUrl: str | None = None
    headline: str | None = None
    location: ApifyProfileLocation | None = None
    currentPosition: list[ApifyCurrentPosition] = Field(default_factory=list)
    experience: list[ApifyExperience] = Field(default_factory=list)


class ApifyPostAuthor(BaseModel):
    name: str | None = None
    linkedinUrl: str | None = None


class ApifyPostedAt(BaseModel):
    # ISO 8601.
    date: str | None = None


class ApifyPostItem(BaseModel):
    id: str | None = None
    linkedinUrl: str | None = None
    content: str | None = None
    author: ApifyPostAuthor | None = None
    postedAt: ApifyPostedAt | None = None


class ApifyCompanyLocation(BaseModel):
    headquarter: bool | None = None
    parsed: ApifyParsedLocation | None = None


class ApifyFoundedOn(BaseModel):
    # LinkedIn only exposes the year.
    year: int | None = None


class ApifyCompanyItem(BaseModel):
    name: str | None = None
    linkedinUrl: str | None = None
    website: str | None = None
    description: str | None = None
    employeeCount: int | None = None
    foundedOn: ApifyFoundedOn | None = None
    logo: str | None = None
    locations: list[ApifyCompanyLocation] = Field(default_factory=list)
