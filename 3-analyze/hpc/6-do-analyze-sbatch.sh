N=$(find ../../results/ -name "*.txt" | wc -l)

sbatch --array=0-$((N-1)) analyze-sbatch.sh ../../results/
