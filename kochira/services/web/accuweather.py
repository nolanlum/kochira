"""
Accuweather forecast.

Get weather data from Accuweather.
"""

import requests

from kochira import config
from kochira.service import Service, background, Config, coroutine
from kochira.userdata import UserData


service = Service(__name__, __doc__)


@service.config
class Config(Config):
    api_key = config.Field(doc="Accuweather API key.")


@service.command(r"!weather(?: (?P<unit>[cf])(?:elsius|ahrenheit)?)?(?: (?P<where>.+))?")
@service.command(r"weather(?: (?:for|in) (?P<where>.+))?(?: in (?P<unit>[cf])(?:elsius|ahrenheit)?)?", mention=True)
@background
@coroutine
def weather(ctx, where=None, unit=None):
    """
    Weather.

    Get the weather for a location.
    """

    if where is None:
        where = ctx.origin

    try:
        geocode = ctx.provider_for("geocode")
    except KeyError:
        ctx.respond(ctx._("Sorry, I don't have a geocode provider loaded."))
        return

    results = yield geocode(where)

    if not results:
        ctx.respond(ctx._("I don't know where \"{where}\" is.").format(
            where=where
        ))
        return

    location = results[0]["geometry"]["location"]

    r = requests.get(
        "https://dataservice.accuweather.com/locations/v1/cities/geoposition/search?apikey={apikey}&q={q}".format(
            apikey=ctx.config.api_key,
            q="{lat},{lng}".format(**location)
    )).json()

    if "Code" in r:
        ctx.respond(ctx._("Sorry, there was an error: {Code}: {Message}").format(
            **r
        ))
        return

    place = "{}, {}".format(
        r['LocalizedName'],
        r['AdministrativeArea']['ID'],
    )

    is_us = r['AdministrativeArea']['CountryID'] == "US"
    force_f = unit and unit.upper() == "F"
    force_c = unit and unit.upper() == "C"
    if (is_us or force_f) and not force_c:
        def _unitize(nonus, us):
            return us
    else:
        def _unitize(nonus, us):
            return nonus

    r = requests.get("https://dataservice.accuweather.com/currentconditions/v1/{location_key}?apikey={apikey}&details=true".format(
        location_key=r['Key'],
        apikey=ctx.config.api_key
    )).json()

    if "Code" in r:
        ctx.respond(ctx._("Sorry, there was an error: {Code}: {Message}").format(
            **r
        ))
        return

    if not r:
        ctx.respond(ctx._("Couldn't find weather for \"{where}\".").format(
            where=where
        ))
        return

    observation = r[0]
    temp = observation["Temperature"][_unitize("Metric", "Imperial")]["Value"]
    feelslike = observation["RealFeelTemperature"][_unitize("Metric", "Imperial")]["Value"]
    wind = observation["Wind"]["Speed"][_unitize("Metric", "Imperial")]["Value"]
    wind_dir = observation["Wind"]["Direction"]["Localized"]
    humidity = observation["RelativeHumidity"]
    dew_point = observation["DewPoint"][_unitize("Metric", "Imperial")]["Value"]
    precip = observation["PrecipitationSummary"]["Precipitation"][_unitize("Metric", "Imperial")]["Value"]
    weather = observation["WeatherText"]

    ctx.respond(ctx._("Today's weather for {place} is: {weather}, {temp} °{cf} (feels like {feelslike} °{cf}), dew point {dew_point} °{cf}, wind from {wind_dir} at {wind} {kphmph}, {humidity}% humidity, {precip} {mmin} precipitation").format(
        place=place,
        weather=weather,
        feelslike=feelslike,
        temp=temp,
        cf=_unitize("C", "F"),
        dew_point=dew_point,
        wind_dir=wind_dir,
        wind=wind,
        kphmph=_unitize("km/h", "mph"),
        humidity=humidity,
        precip=precip,
        mmin=_unitize("mm", "in")
    ))


