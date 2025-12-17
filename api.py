import httpx
from fastapi import FastAPI, HTTPException
from datetime import date

app = FastAPI()

TEAM_ID = 121  # Mets
MLB_SCHEDULE_API = "https://statsapi.mlb.com/api/v1/schedule?sportId=1&teamId={team_id}&date={today}"
MLB_LIVE_FEED = "https://statsapi.mlb.com/api/v1.1/game/{gamePk}/feed/live"

def format_play(play, teams):
    # your existing formatting logic
    away_score = play["result"].get("awayScore", 0)
    home_score = play["result"].get("homeScore", 0)
    return {
        "Game": {
            "Inning": {
                "Half": play["about"].get("halfInning"),
                "Inning#": play["about"].get("inning")
            },
            "Score": {
                f"{teams['away']}": away_score,
                f"{teams['home']}": home_score
            },
            "Game event": play["result"].get("description", "")
        }
    }

async def get_mets_game_pk(today: str = None):
    if not today:
        #today = date.today().isoformat()
        today = "2025-09-19"

    url = MLB_SCHEDULE_API.format(team_id=TEAM_ID, today=today)
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url)
    if r.status_code != 200:
        raise HTTPException(status_code=500, detail="Failed to fetch schedule")

    data = r.json()
    total_games = data.get("totalGames", 0)
    if total_games > 0:
        return data["dates"][0]["games"][0]["gamePk"]
    return None

@app.get("/formatted/game/today")
async def get_latest_completed_play_today():
    game_pk = await get_mets_game_pk()
    if not game_pk:
        return {"message": "No Mets game today"}

    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(MLB_LIVE_FEED.format(gamePk=game_pk))
    if r.status_code != 200:
        raise HTTPException(status_code=500, detail="Failed to fetch MLB live feed")

    data = r.json()

    teams_data = data.get("gameData", {}).get("teams", {})
    teams = {
        "home": teams_data.get("home", {}).get("name", "Unknown Home"),
        "away": teams_data.get("away", {}).get("name", "Unknown Away"),
    }

    all_plays = data.get("liveData", {}).get("plays", {}).get("allPlays", [])
    if not all_plays:
        return {"message": "No play data yet"}

    for play in reversed(all_plays):
        if play.get("result") and play.get("about", {}).get("isComplete"):
            return format_play(play, teams)

    return {"message": "No completed at-bats yet"}
