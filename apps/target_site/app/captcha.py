from dataclasses import dataclass
from io import BytesIO
import random
import string
import uuid

from PIL import Image, ImageDraw, ImageFont


@dataclass
class CaptchaChallenge:
    challenge_id: str
    expected_answer: str


class CaptchaStore:
    def __init__(self) -> None:
        self._answers: dict[str, str] = {}

    def create(self) -> CaptchaChallenge:
        answer = "".join(random.choice(string.ascii_uppercase + string.digits) for _ in range(5))
        challenge_id = str(uuid.uuid4())
        self._answers[challenge_id] = answer
        return CaptchaChallenge(challenge_id=challenge_id, expected_answer=answer)

    def verify(self, challenge_id: str, answer: str) -> bool:
        expected = self._answers.get(challenge_id)
        if expected is None:
            return False
        ok = expected.upper() == answer.strip().upper()
        if ok:
            self._answers.pop(challenge_id, None)
        return ok

    def render_png(self, challenge_id: str) -> bytes:
        answer = self._answers.get(challenge_id)
        if answer is None:
            raise KeyError(challenge_id)

        image = Image.new("RGB", (180, 70), color=(250, 250, 250))
        draw = ImageDraw.Draw(image)
        font = ImageFont.load_default()
        draw.text((35, 25), answer, fill=(20, 20, 20), font=font)

        for x in range(0, 180, 18):
            draw.line((x, 0, 180 - x, 70), fill=(180, 180, 180), width=1)

        output = BytesIO()
        image.save(output, format="PNG")
        return output.getvalue()

