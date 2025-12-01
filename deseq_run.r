#!/usr/bin/env Rscript

suppressMessages({
  library(DESeq2)
  library(readr)
  library(dplyr)
})

args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 3) { stop("Usage: Rscript deseq_run.R counts.csv metadata.csv output_dir") }

count_file <- args[1]
meta_file  <- args[2]
outdir     <- args[3]

message("=== Loading Input Files ===")

counts <- read.csv(count_file, row.names = 1, check.names = FALSE)
meta   <- read.csv(meta_file, row.names = 1, check.names = FALSE)

# Validate sample matching
if (!all(colnames(counts) %in% rownames(meta))) {
  stop("Sample names in counts do NOT match metadata row names.")
}

meta <- meta[colnames(counts), , drop = FALSE]

if (!"condition" %in% colnames(meta)) {
  stop("Metadata must contain a column named 'condition'")
}

meta$condition <- factor(meta$condition)

# Cleanup counts
counts <- counts[rowSums(counts) > 0, ]
counts <- round(counts)

message("Counts loaded: ", nrow(counts), " genes x ", ncol(counts), " samples")
message("Conditions: ", paste(levels(meta$condition), collapse = ", "))

dds <- DESeqDataSetFromMatrix(
  countData = counts,
  colData   = meta,
  design    = ~ condition
)

message("Estimating size factors...")
dds <- estimateSizeFactors(dds)

# ----------------------------------------
# DISPERSION ESTIMATION (robust version)
# ----------------------------------------
message("Estimating dispersions...")

dispersion_ok <- TRUE
tryCatch({
  dds <- estimateDispersions(dds)
}, error = function(e) {
  message("Standard dispersion estimation FAILED. Falling back to gene-wise dispersions.")
  dispersion_ok <<- FALSE
})

if (!dispersion_ok) {
  dds <- estimateDispersionsGeneEst(dds)

  # FINALIZE DISPERSIONS — REQUIRED FOR TESTING
  mcols(dds)$dispersion <- mcols(dds)$dispGeneEst
  dispersions(dds)      <- mcols(dds)$dispGeneEst
}

# ----------------------------------------
# Differential Expression
# ----------------------------------------
message("Running differential expression test...")
dds <- nbinomWaldTest(dds)

res <- results(dds)
res <- res[order(res$padj), ]

# ----------------------------------------
# OUTPUT DIRECTORY
# ----------------------------------------
if (!dir.exists(outdir)) { dir.create(outdir, recursive = TRUE) }

write.csv(
  as.data.frame(res),
  file = file.path(outdir, "deseq2_results.csv")
)

# Normalized count matrix
norm_counts <- counts(dds, normalized = TRUE)
write.csv(
  norm_counts,
  file = file.path(outdir, "normalized_counts.csv")
)

# ----------------------------------------
# VST with safe fallback
# ----------------------------------------
message("Generating VST matrix...")

vsd <- NULL
tryCatch({
  vsd <- vst(dds, blind = TRUE)
}, error = function(e) {
  message("vst() failed — switching to varianceStabilizingTransformation() instead.")
  vsd <<- varianceStabilizingTransformation(dds, blind = TRUE)
})

write.csv(
  assay(vsd),
  file = file.path(outdir, "vst_matrix.csv")
)

message("=== DESeq2 Analysis Complete ===")
message("Results saved to: ", outdir)

