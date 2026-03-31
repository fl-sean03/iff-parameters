# IFF Parameterization Pipeline — Design Document

## Problem Statement

Going from a new molecular structure to validated IFF parameters takes days to weeks of manual work:
1. Manual atom type assignment in Materials Studio (hours)
2. Searching through 1000+ line .frc files for "similar" types (tedious, error-prone)
3. Manual charge assignment with neutrality constraints
4. Running 3-4 validation simulations per iteration
5. Comparing to experimental values
6. Iterating until convergence (days)

**This is the #1 bottleneck in the lab's computational workflow.**

## Proposed Solution: Auto-Type + Human Review + Agent Iteration

### Phase 1: Auto-Typing (Best Guess)

An automated system that assigns IFF atom types based on chemical environment:

```
Input:  Molecular structure (CIF, PDB, MOL2, CAR/MDF)
Output: Atom type assignments with confidence scores

Method:
  1. Parse structure → extract atom connectivity
  2. For each atom, determine:
     - Element
     - Hybridization (sp, sp2, sp3)
     - Number and type of neighbors
     - Ring membership (3/4/5/6-member, aromatic)
     - Functional group context
  3. Match against IFF atom type rules
  4. Assign confidence score (high/medium/low)
     - High: exact match to known IFF type definition
     - Medium: match by analogy to similar chemical environment
     - Low: no good match, using closest element-based default
```

**Existing prior art:**
- LUNAR (CMMRLab) — does PCFF-IFF and CVFF-IFF auto-typing
- CGenFF — does CHARMM auto-typing with penalty scores
- OpenFF SMIRNOFF — uses SMARTS patterns for direct chemical perception

**What we need to encode:**
- IFF atom type definitions (from .frc `#atom_types` + `#equivalence` sections)
- Typing rules (from .dat template files on hendrikheinz GitHub)
- Element-to-connectivity tables
- Special cases (metals, surface oxygens, mineral-specific types)

### Phase 2: Human Review (Judgment Calls)

The auto-typer flags uncertain assignments. The human reviews only these:

```
Auto-typed structure:
  C1  → c3  (sp3 carbon, HIGH confidence)
  C2  → cp  (aromatic carbon, HIGH confidence)
  O1  → o'  (carbonyl oxygen, HIGH confidence)
  O2  → ???  (bridging oxide, LOW confidence — needs review)
  Ti1 → ???  (surface titanium, LOW confidence — needs review)

Human reviews O2 and Ti1, selects from suggested alternatives.
```

The dashboard Upload page could be extended to show this review interface.

### Phase 3: Charge Assignment

After atom types are assigned, charges need to be set:

```
Method options:
  1. Bond increment method (from .frc #bond_increments section)
     - Automated, but only works if all bond pairs have increments
  2. Literature values (from published IFF papers)
     - High quality but requires matching to specific surface model
  3. Extended Born Model (Heinz 2004)
     - Gold standard for IFF, but requires expert judgment
  4. QM-derived (Mulliken, RESP, Bader from DFT)
     - Fallback, less accurate for IFF philosophy

Constraint: total charge must be neutral (or match system charge)
```

### Phase 4: Agent-Driven Iterative Refinement

The ScienceAgent handles the optimize → simulate → compare → adjust loop:

```
Agent workflow:
  1. Load auto-typed + human-reviewed parameters
  2. Set up validation simulation suite:
     - Lattice constants (NPT equilibration)
     - Surface energy (slab calculation)
     - Density (bulk liquid/solid)
     - Contact angle or wetting (if applicable)
  3. Run simulations (LAMMPS via CLI)
  4. Parse results, compare to experimental benchmarks
  5. If converged → ingest final parameters into iff-parameters
  6. If not → adjust parameters (gradient-free optimization):
     - Scale LJ epsilon ±5-10%
     - Adjust charges within neutrality constraint
     - Re-run and compare
  7. Repeat until convergence criteria met
```

**Benchmark database needed:**
For each material, store experimental reference values:
- Lattice constants (Å)
- Surface energy (J/m²)
- Bulk density (g/cm³)
- Elastic constants (GPa)
- Bulk modulus (GPa)

These come from literature and are material-specific.

## Implementation Roadmap

### Sprint 1: Auto-Typer MVP
- Parse IFF atom type definitions from existing .frc files
- Implement element + hybridization + neighbor matching
- Handle the "easy" 80% (standard organic + metal atoms)
- Output: typed structure with confidence scores
- Validate against known systems (manually typed structures)

### Sprint 2: Review Interface
- Extend dashboard with "Review" page for flagged assignments
- Show structure visualization (optional, could use 3Dmol.js)
- Human selects from suggested alternatives for low-confidence atoms
- Export reviewed assignments

### Sprint 3: Charge Pipeline
- Implement bond increment method (auto from .frc data)
- Charge neutrality enforcement
- Literature charge lookup for known surface models

### Sprint 4: Agent Iteration Loop
- Define validation simulation templates (LAMMPS input files)
- Curate experimental benchmark database (10-20 materials initially)
- ScienceAgent skill for iterative refinement
- Convergence criteria and reporting

### Sprint 5: Integration
- Full pipeline: structure → auto-type → review → charge → simulate → converge
- Ingest converged parameters into iff-parameters
- Provenance tracking for the full pipeline

## Dependencies

- **USM v2.0** — structure I/O (already done)
- **UPM v2.0** — parameter management (already done)
- **iff-parameters** — parameter storage (already done)
- **ScienceAgent** — LAMMPS simulation skill (already done)
- **IFF atom type rules** — need to extract from .frc + .dat files
- **Experimental benchmark data** — need to curate from literature

## Open Questions

1. Should the auto-typer use rule-based matching or ML-based prediction?
   - Rule-based: interpretable, uses existing IFF definitions, but brittle
   - ML-based: more generalizable but requires training data and is less interpretable
   - Recommendation: start rule-based, add ML later if needed

2. How to handle truly novel chemical environments?
   - IFF can't parameterize everything — some systems need DFT
   - The auto-typer should clearly flag "IFF cannot handle this"

3. Who approves the final parameters?
   - PI must review before ingestion into canonical iff-parameters
   - Agent can ingest into a staging/draft area for review

4. How generalizable does this need to be?
   - Start with the 3-5 molecules/materials the lab is currently working on
   - Generalize later based on what patterns emerge
