"""
Pirate Weather forecast.

Get weather data from Pirate Weather.
"""

import requests

from kochira import config
from kochira.service import Service, background, Config
from kochira.userdata import UserData


service = Service(__name__, __doc__)


@service.config
class Config(Config):
    api_key = config.Field(doc="Pirate Weather API key.")


@service.command(r"!weather(?: (?P<unit>[cf])(?:elsius|ahrenheit)?)?(?: (?P<where>.+))?")
@service.command(r"weather(?: (?:for|in) (?P<where>.+))?(?: in (?P<unit>[cf])(?:elsius|ahrenheit)?)?", mention=True)
@background
async def weather(ctx, where=None, unit=None):
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

    results = await geocode(where)

    if not results:
        ctx.respond(ctx._("I don't know where \"{where}\" is.").format(
            where=where
        ))
        return

    def address_component(component_type):
        filtered_components = [x for x in results[0]['address_components'] if component_type in x['types']]
        return filtered_components[0] if filtered_components else None

    country = address_component('country')

    is_us = country['short_name'] == "US"
    force_f = unit and unit.upper() == "F"
    force_c = unit and unit.upper() == "C"
    if (is_us or force_f) and not force_c:
        def _unitize(nonus, us):
            return us
    else:
        def _unitize(nonus, us):
            return nonus

    location = results[0]["geometry"]["location"]

    r = requests.get(
        "https://api.pirateweather.net/forecast/{apikey}/{q}?units={units}&exclude=minutely,hourly,alerts&version=2".format(
            apikey=ctx.config.api_key,
            q="{lat},{lng}".format(**location),
            units=_unitize("si", "us")
    )).json()

    if "detail" in r or "message" in r:
        error_message = r.get("detail") or r["message"]
        ctx.respond(ctx._("Sorry, there was an error: {error}").format(
            error=error_message
        ))
        return

    if not r:
        ctx.respond(ctx._("Couldn't find weather for \"{where}\".").format(
            where=where
        ))
        return

    locality = address_component('locality')['short_name'] or 'Unknown'
    admin_area_L1 = address_component('administrative_area_level_1')['short_name'] or 'Unknown'
    place = "{}, {}".format(
        locality,
        admin_area_L1
    )

    observation = r["currently"]
    temp = round(observation["temperature"], 1)
    feelslike = round(observation["apparentTemperature"], 1)
    wind = round(observation["windSpeed"], 1)
    wind_dir = bearing_to_direction(observation["windBearing"])
    humidity = int(observation["humidity"] * 100)
    dew_point = round(observation["dewPoint"], 1)
    precip = round(r["daily"].get("precipAccumulation") or 0, 1)
    weather = observation["summary"]

    ctx.respond(ctx._("Today's weather for {place} is: {weather}, {temp} °{cf} (feels like {feelslike} °{cf}), dew point {dew_point} °{cf}, wind from {wind_dir} at {wind} {kphmph}, {humidity}% humidity, {precip} {cmin} precipitation").format(
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
        cmin=_unitize("cm", "in")
    ))


def bearing_to_direction(degrees):
    cardinals = ['N', 'N/NE', 'NE', 'E/NE', 'E', 'E/SE', 'SE', 'S/SE', 'S', 'S/SW', 'SW', 'W/SW', 'W', 'W/NW', 'NW', 'N/NW']
    return cardinals[int(degrees / 22.5 + .5) % 16]
