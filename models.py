from dataclasses import dataclass, field, asdict
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

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "main_character": self.main_character,
            "rating": self.rating,
            "games": self.games,
            "deviation": self.deviation,
            "last_played": self.last_played,
        }

    @staticmethod
    def from_dict(data: dict) -> "Player":
        return Player(
            id=data["id"],
            name=data.get("name", ""),
            main_character=data.get("main_character", ""),
            rating=data.get("rating", 0),
            games=data.get("games", 0),
            deviation=data.get("deviation", 0),
            last_played=data.get("last_played", ""),
        )
    def __str__(self):
            print('str called')
            return json.dumps(asdict(self))