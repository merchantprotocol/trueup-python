# The barndominium domain. Everything the engine knows about this kind of job
# lives here, not in Python. Point the engine at a different kind of job by
# writing a file like this one.

# Facts to read from each past estimate and each new request.
#   keys      labels the fact goes by in "Label: value" lines (matched fuzzily)
#   patterns  regexes whose first group is the value
#   count_of  a noun; the number (or number word) before it is the value
#   not_after skip count_of matches preceded by this
#   zero_if   if this appears, the fact is 0
facts = {
  width:        {patterns: [r"\b(\d{2,3})\s*'?\s*(?:x|by|×)\s*\d{2,3}\b"]},
  length:       {patterns: [r"\b\d{2,3}\s*'?\s*(?:x|by|×)\s*(\d{2,3})\b"]},
  eave:         {keys: ["eave height ft", "eave"],
                 patterns: [r"(\d{1,2})\s*(?:'|ft\.?|foot|-foot)?\s*(?:eaves?|sidewalls?|walls)\b"]},
  living:       {keys: ["living area sf", "heated sf", "conditioned sf", "sqft living"],
                 patterns: [r"([\d,]{3,6})\s*(?:sf|sq\.?\s*ft\.?|square feet|heated|conditioned)\s*(?:of\s+)?(?:heated\s+|conditioned\s+)?(?:sf|sq\.?\s*ft\.?|square feet)?\s*(?:of\s+)?(?:living|heated|conditioned)",
                            r"([\d,]{3,6})\s+(?:heated|living|conditioned)"]},
  baths:        {keys: ["baths", "bathrooms"], count_of: r"bath(?:room)?s?"},
  garage_doors: {keys: ["overhead doors", "garage doors"], count_of: r"(?:overhead|roll-up|garage|shop)\s+doors?"},
  windows:      {keys: ["windows", "window count"], count_of: r"windows?"},
  entry_doors:  {keys: ["entry doors", "man doors"], count_of: r"(?:entry|exterior|man)?\s*doors?",
                 not_after: r"overhead|roll-up|garage|shop"},
  porch:        {patterns: [r"([\d,]{2,5})\s*(?:sf|sq\.?\s*ft\.?|square feet)\s+covered\s+porch"],
                 zero_if: r"\bno porch\b"}
}

# A request can't be priced without these.
required = ["width", "length", "eave", "living"]

# What a cost might scale with, as formulas over facts. The engine tries each one
# (plus a flat lump sum and a share of the rest of the job) and keeps whichever
# gives the steadiest rate across past jobs, or whichever the estimates' own
# quantities point to.
drivers = {
  footprint:    "width * length",
  living:       "living",
  envelope:     "2 * (width + length) * eave + width * length * 1.08",
  perimeter:    "2 * (width + length)",
  baths:        "baths",
  garage_doors: "garage_doors",
  windows:      "windows",
  entry_doors:  "entry_doors",
  porch:        "porch"
}

# Cost categories. Short examples are enough; the engine learns more phrasings.
categories = [
  {id: "site_prep",       label: "Site preparation",                  examples: ["site work and grading", "excavation"]},
  {id: "foundation",      label: "Foundation / concrete slab",        examples: ["concrete slab", "footings"]},
  {id: "building_kit",    label: "Steel building materials package",  examples: ["metal building kit", "steel frame and wall/roof panels"]},
  {id: "erection",        label: "Steel building erection labor",     examples: ["erect building", "crane and erection crew"]},
  {id: "framing",         label: "Interior framing",                  examples: ["interior walls framing", "rough carpentry"]},
  {id: "windows",         label: "Windows",                           examples: ["windows supplied and installed"]},
  {id: "entry_doors",     label: "Exterior entry doors",              examples: ["front door", "exterior walk doors"]},
  {id: "garage_doors",    label: "Overhead / garage doors",           examples: ["overhead door", "roll up door"]},
  {id: "insulation",      label: "Insulation",                        examples: ["spray foam", "fiberglass insulation"]},
  {id: "plumbing",        label: "Plumbing",                          examples: ["plumbing rough in", "plumbing fixtures set"]},
  {id: "electrical",      label: "Electrical",                        examples: ["electrical wiring", "electrical panel and service"]},
  {id: "hvac",            label: "HVAC heating and cooling",          examples: ["heat pump", "furnace and air conditioning"]},
  {id: "drywall",         label: "Drywall",                           examples: ["drywall", "wallboard hang and finish"]},
  {id: "paint",           label: "Interior painting",                 examples: ["paint interior walls"]},
  {id: "flooring",        label: "Flooring",                          examples: ["floor covering", "vinyl plank or tile floors"]},
  {id: "cabinets",        label: "Kitchen cabinets and countertops",  examples: ["cabinets", "countertops"]},
  {id: "trim_doors",      label: "Interior doors and trim",           examples: ["interior doors", "baseboard and casing trim"]},
  {id: "fixtures",        label: "Appliances and fixture allowance",  examples: ["appliances", "light fixtures allowance"]},
  {id: "gutters",         label: "Gutters",                           examples: ["gutters and downspouts"]},
  {id: "porch",           label: "Covered porch",                     examples: ["porch", "lean-to roof"]},
  {id: "well",            label: "Water well",                        examples: ["well and pump"]},
  {id: "water_tap",       label: "City water connection",             examples: ["water meter and tap"]},
  {id: "septic",          label: "Septic system",                     examples: ["septic tank and leach field"]},
  {id: "sewer_tap",       label: "City sewer connection",             examples: ["sewer connection fee"]},
  {id: "permits",         label: "Permits and fees",                  examples: ["building permit"]},
  {id: "cleanup",         label: "Cleanup and waste removal",         examples: ["dumpster rental", "final cleaning"]},
  {id: "overhead_profit", label: "Contractor overhead and profit",    examples: ["overhead and profit", "GC markup"]}
]
