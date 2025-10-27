"""
Workflow state management
"""


class WorkflowState:
    """Maintains state of the ADCP dataset throughout workflow steps"""

    def __init__(self):
        self.raw_ds = None          # Original dataset after conversion
        self.ds = None              # Working dataset (after QC steps)
        self.ds_avg = None          # Averaged dataset
        self.avg_tool = None        # ADPBinner instance
        self.plots = {}             # Cached matplotlib figures
        self.parameters = {}        # User-set parameters

    def reset(self):
        """Reset all state"""
        self.raw_ds = None
        self.ds = None
        self.ds_avg = None
        self.avg_tool = None
        self.plots.clear()
        self.parameters.clear()

    def load_dataset(self, dataset):
        """Load initial dataset"""
        self.raw_ds = dataset
        self.ds = dataset.copy(deep=True)

    def has_dataset(self):
        """Check if dataset is loaded"""
        return self.ds is not None

    def get_dataset_info(self):
        """Get basic info about current dataset"""
        if not self.has_dataset():
            return "No dataset loaded"

        dims = ", ".join([f"{k}={v}" for k, v in self.ds.dims.items()])
        vars_count = len(self.ds.data_vars)
        return f"Dimensions: {dims} | Variables: {vars_count}"