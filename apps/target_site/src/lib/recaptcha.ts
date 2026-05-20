const GOOGLE_VERIFY_URL = "https://www.google.com/recaptcha/api/siteverify";

// Chaves de teste do Google que sempre passam — úteis para dev local.
const DEFAULT_SITE_KEY = "6LeIxAcTAAAAAJcZVRqyHh71UMIEGNQ_MXjiZKhI";
const DEFAULT_SECRET_KEY = "6LeIxAcTAAAAAGG-vFI1TnRWxMZNFuojJ4WifJWe";

export function getRecaptchaSiteKey(): string {
  return process.env.RECAPTCHA_SITE_KEY || DEFAULT_SITE_KEY;
}

function getRecaptchaSecretKey(): string {
  return process.env.RECAPTCHA_SECRET_KEY || DEFAULT_SECRET_KEY;
}

type GoogleVerifyResponse = {
  success: boolean;
  "error-codes"?: string[];
};

export async function verifyRecaptcha(token: string): Promise<boolean> {
  if (!token) {
    return false;
  }

  const body = new URLSearchParams({
    secret: getRecaptchaSecretKey(),
    response: token
  });

  try {
    const response = await fetch(GOOGLE_VERIFY_URL, {
      method: "POST",
      headers: { "content-type": "application/x-www-form-urlencoded" },
      body: body.toString()
    });

    if (!response.ok) {
      return false;
    }

    const data = (await response.json()) as GoogleVerifyResponse;
    return data.success === true;
  } catch {
    return false;
  }
}
