from dataclasses import dataclass, asdict
import json

@dataclass
class Player:
    id: str
    name: str = ""
    main_character: str = ""
    rating: int = 0
    games: int = 0
    deviation: int = 0
    last_played: str = ""

    def __str__(self):
        print('str called')
        return json.dumps(asdict(self))
    