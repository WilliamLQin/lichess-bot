#!/bin/bash

# enable job control
set -m

# move to directory of tournament.sh
cd "$(dirname "$0")"

if ! (command -v python3 >/dev/null 2>&1)
then
  echo "python3 not installed!"
  exit 1
fi

if ! [ -r tournament_teams.txt ];
then
  echo "tournament_teams.txt not found!"
  exit 1
fi

if ! [ -r tournament_bot_api_tokens.txt ];
then
  echo "tournament_bot_api_tokens.txt not found!"
  exit 1
fi

if ! [ -r tournament_challenge_api_tokens.txt ];
then
  echo "tournament_challenge_api_tokens.txt not found!"
  exit 1
fi

# install dependencies
python3 -m pip install -r requirements.txt

# read tournament teams
IFS=$'\n' read -d '' -r -a lines < tournament_teams.txt

# read api tokens
IFS=$'\n' read -d '' -r -a bot_tokens < tournament_bot_api_tokens.txt
IFS=$'\n' read -d '' -r -a tokens < tournament_challenge_api_tokens.txt

echo_teams() {
  echo "Teams:"

  length=${#lines[@]}
  for (( i=0; i<${length}; i++ ));
  do
    echo "  $i: ${lines[i]}"
  done
}

# var 1 is team 1 index, var 2 is team 2 index
stage_teams() {
  cp ./engines/${lines[$1]}.sh ./engines/_bot1/CO456Engine
  cp ./engines/${lines[$2]}.sh ./engines/_bot2/CO456Engine

  # make sure shell scripts are executable
  chmod +x ./engines/_bot1/CO456Engine
  chmod +x ./engines/_bot2/CO456Engine
}

run_bots() {
  echo "Running bots... type CTRL-C to terminate both bots (it may take a while)"
  (trap 'kill 0' SIGINT; python3 lichess-bot.py --config config_bot1.yml > /dev/null & python3 lichess-bot.py --config config_bot2.yml > /dev/null)
  echo "Bots terminated!"
}

# Bot 1 (white) will challenge bot 2 (black)
# var 1 is WHITE team index, var 2 is BLACK team index
create_game() {
  # create challenge and open the url to the game
  local id=$(curl -X POST \
      -d 'color=white' -d 'clock.limit=180' -d 'clock.increment=0' \
      -d "acceptByToken=${tokens[1]}" \
      -H "Authorization: Bearer ${tokens[0]}" \
      https://lichess.org/api/challenge/co456_bot2 |
    python3 -c "
import sys, json, webbrowser, requests;
resp = json.load(sys.stdin)['game'];
url = resp['url'];
id = resp['id'];
print(id);
webbrowser.open_new_tab(url);")

  curl -X POST -d "text=White: ${lines[$1]}, Black: ${lines[$2]}" \
      -d 'room=spectator' -H "Authorization: Bearer ${bot_tokens[0]}" \
      https://lichess.org/api/bot/game/${id}/chat
  echo ""
}

echo "Welcome to the CO 456 tournament oversight program."

while :
do
  echo ""
  echo "Ready to play next game! Type CTRL-C to exit."
  echo_teams
  # loop infinitely
  read -p "Enter team number of team to play WHITE: " tw
  read -p "Enter team number of team to play BLACK: " tb

  echo "Note: to proceed to next game type CTRL-C to terminate bots (it may take a while)"
  read -p "Press enter to continue..."

  stage_teams $tw $tb
  create_game $tw $tb
  run_bots
done

