export const VALID_CATEGORIES = new Set(["pendant", "ring", "earring", "bracelet", "chain"]);
export const CATEGORY_DISPLAY_ORDER = ["pendant", "ring", "earring", "bracelet", "chain"];
export const VALID_CARATS = new Set(["0.1", "0.2", "0.3", "0.5", "1.0"]);
export const VALID_CARATS_CHAIN = new Set(["3fen", "4fen"]);
export const VALID_GOLDS = new Set(["9k", "14k", "18k", "pt950", "s925"]);
export const GOLD_DISPLAY_ORDER = ["9k", "14k", "18k", "pt950", "s925"] as const;
export const GOLDS_REQUIRING_COLOR = new Set(["14k", "18k"]);
export const GOLD_WHITE_ONLY = new Set(["9k"]);
export const VALID_COLORS = new Set(["white", "yellow", "rose"]);
export const RING_SIZE_MIN = 5;
export const RING_SIZE_MAX = 18;
export const ENGRAVING_MAX_LENGTH = 10;
export const GIRDLE_ENGRAVING_CATEGORIES = new Set(["ring"]);
export const CHAIN_LENGTH_OPTIONS_CM = [35, 40, 45, 50, 55, 60] as const;
export const BRACELET_LENGTH_OPTIONS_CM = [15, 16, 17, 18, 19, 20, 21] as const;

export function sortGolds(golds: Iterable<string>): string[] {
  const order = Object.fromEntries(GOLD_DISPLAY_ORDER.map((g, i) => [g, i]));
  return [...golds].sort((a, b) => (order[a] ?? 999) - (order[b] ?? 999));
}

export type SubmissionInput = Record<string, unknown>;

export type CleanedSubmission = {
  category?: string;
  gold?: string;
  type?: string;
  carat?: string;
  color?: string;
  ringSize?: number;
  engravingBand?: string;
  engravingGirdle?: string;
  lengthCm?: number;
  includeChain?: boolean;
  chainProductId?: string;
  chainGold?: string;
  chainColor?: string;
  chainLength?: number;
  diamondKind?: string;
  fancyColor?: string;
  stoneCount?: number;
  diamondShape?: string;
};

export function validateSubmissionFields(
  data: SubmissionInput,
  partial = false,
): { cleaned: CleanedSubmission; error: string | null } {
  const errors: string[] = [];
  const cleaned: CleanedSubmission = {};

  function checkChoice(key: string, valid: Set<string>, required = true) {
    const val = data[key];
    if (val == null) {
      if (required && !partial) errors.push(`${key} is required`);
    } else if (!valid.has(String(val))) {
      errors.push(`invalid ${key}`);
    } else {
      (cleaned as Record<string, string>)[key] = String(val);
    }
  }

  checkChoice("category", VALID_CATEGORIES);
  checkChoice("gold", VALID_GOLDS);

  const typeVal = data.type;
  if (typeVal == null) {
    if (!partial) errors.push("type is required");
  } else {
    cleaned.type = String(typeVal);
  }

  const cat = cleaned.category ?? String(data.category ?? "");
  const carat = data.carat;
  if (carat == null) {
    if (!partial) errors.push("carat is required");
  } else {
    const validC = cat === "chain" ? VALID_CARATS_CHAIN : VALID_CARATS;
    if (!validC.has(String(carat))) errors.push("invalid carat");
    else cleaned.carat = String(carat);
  }

  const color = data.color;
  if (color != null && !VALID_COLORS.has(String(color))) {
    errors.push("invalid color");
  } else if (color != null) {
    cleaned.color = String(color);
  }

  if (!partial) {
    const gold = cleaned.gold;
    if (gold && GOLD_WHITE_ONLY.has(gold)) {
      if (cleaned.color != null && cleaned.color !== "white") {
        errors.push("9k only supports white");
      } else {
        cleaned.color = "white";
      }
    } else if (gold && GOLDS_REQUIRING_COLOR.has(gold) && !cleaned.color) {
      errors.push("color is required for gold alloys");
    }
  }

  const ringSize = data.ringSize;
  if (ringSize != null) {
    const n = Number(ringSize);
    if (!Number.isFinite(n) || n < RING_SIZE_MIN || n > RING_SIZE_MAX) {
      errors.push("invalid ringSize");
    } else {
      cleaned.ringSize = n;
    }
  }

  if (!partial && cleaned.category === "ring" && cleaned.ringSize == null) {
    errors.push("ringSize is required for rings");
  }

  function cleanEngraving(key: "engravingBand" | "engravingGirdle", permitted: Set<string>) {
    const raw = data[key];
    if (raw == null) return;
    const value = String(raw)
      .trim()
      .split("")
      .filter((c) => c.charCodeAt(0) >= 32)
      .join("");
    if (cleaned.category && !permitted.has(cleaned.category)) {
      if (value) errors.push(`${key} is not available for this category`);
    } else if (value.length > ENGRAVING_MAX_LENGTH) {
      errors.push(`${key} must be at most ${ENGRAVING_MAX_LENGTH} characters`);
    } else if (value && key === "engravingGirdle" && !/^[A-Za-z0-9]{1,10}$/.test(value)) {
      errors.push(`${key} must be 1–10 letters or digits`);
    } else if (value) {
      cleaned[key] = value;
    }
  }

  cleanEngraving("engravingBand", new Set(["ring"]));
  cleanEngraving("engravingGirdle", GIRDLE_ENGRAVING_CATEGORIES);

  function cleanChainLength(
    key: "lengthCm" | "chainLength",
    required: boolean,
    allowed: readonly number[],
  ) {
    const raw = data[key];
    if (raw == null) {
      if (required) errors.push(`${key} is required`);
      return null;
    }
    const value = Number.parseInt(String(raw), 10);
    if (!allowed.includes(value)) {
      errors.push(`invalid ${key}`);
      return null;
    }
    return value;
  }

  if (cleaned.category === "chain") {
    const length = cleanChainLength("lengthCm", !partial, CHAIN_LENGTH_OPTIONS_CM);
    if (length != null) cleaned.lengthCm = length;
  }

  if (cleaned.category === "bracelet") {
    const length = cleanChainLength("lengthCm", !partial, BRACELET_LENGTH_OPTIONS_CM);
    if (length != null) cleaned.lengthCm = length;
  }

  const includeChain = Boolean(data.includeChain);
  let diamondKind = data.diamondKind != null ? String(data.diamondKind) : "white";
  if (!["white", "fancy"].includes(diamondKind)) errors.push("invalid diamondKind");
  else cleaned.diamondKind = diamondKind;

  let diamondShape = data.diamondShape != null ? String(data.diamondShape) : "round";
  if (!["round"].includes(diamondShape)) errors.push("invalid diamondShape");
  else cleaned.diamondShape = diamondShape;

  if (cat === "chain") {
    cleaned.diamondKind = "white";
    cleaned.diamondShape = "round";
  } else if (cleaned.diamondKind === "fancy") {
    const fancyColor = data.fancyColor;
    if (fancyColor == null) {
      if (!partial) errors.push("fancyColor is required for fancy diamonds");
    } else if (!["yellow", "pink", "blue"].includes(String(fancyColor))) {
      errors.push("invalid fancyColor");
    } else {
      cleaned.fancyColor = String(fancyColor);
    }
    if (cleaned.carat && !partial) {
      const v = Number.parseFloat(String(cleaned.carat));
      if (!Number.isFinite(v) || v < 0.3) {
        errors.push("fancy diamonds require carat 0.30 or above");
      }
    }
    if (cat === "earring") {
      const stoneCount = data.stoneCount;
      if (stoneCount == null) {
        if (!partial) cleaned.stoneCount = 2;
      } else {
        const n = Number.parseInt(String(stoneCount), 10);
        if (![2, 3, 4].includes(n)) errors.push("invalid stoneCount");
        else cleaned.stoneCount = n;
      }
    }
  } else {
    cleaned.diamondKind ??= "white";
    cleaned.diamondShape ??= "round";
  }

  if (cat === "earring") cleaned.stoneCount = 2;

  if (cleaned.category === "pendant") {
    cleaned.includeChain = includeChain;
    if (includeChain) {
      if (!data.chainProductId) {
        if (!partial) errors.push("chainProductId is required");
      } else {
        cleaned.chainProductId = String(data.chainProductId);
      }
      if (data.chainGold == null || String(data.chainGold) === "") {
        if (!partial) errors.push("chainGold is required");
      } else if (!VALID_GOLDS.has(String(data.chainGold))) {
        errors.push("invalid chainGold");
      } else {
        cleaned.chainGold = String(data.chainGold);
      }
      if (data.chainColor == null || String(data.chainColor) === "") {
        if (!partial) errors.push("chainColor is required");
      } else if (!VALID_COLORS.has(String(data.chainColor))) {
        errors.push("invalid chainColor");
      } else {
        cleaned.chainColor = String(data.chainColor);
      }
      const length = cleanChainLength("chainLength", !partial, CHAIN_LENGTH_OPTIONS_CM);
      if (length != null) cleaned.chainLength = length;
    }
  }

  return { cleaned, error: errors.length ? errors.join("; ") : null };
}
