def _init_filter_panel(self):
    """Initialize and set up the filter panel."""
    if not FilterPanel:
        return
    
    # Create filter panel
    self._filter_panel = FilterPanel(self)
    
    # Add to main layout, initially hidden
    if hasattr(self.layout(), "addWidget"):
        self.layout().addWidget(self._filter_panel)
        if hasattr(self._filter_panel, "setVisible"):
            self._filter_panel.setVisible(False)
            
    # Connect filter panel signals
    if hasattr(self._filter_panel, "filter_changed"):
        self._filter_panel.filter_changed.connect(self._on_filter_criteria_changed)
        
    # Connect filter button toggle
    if hasattr(self, "_filter_btn") and hasattr(self._filter_btn, "toggled"):
        self._filter_btn.toggled.connect(self._toggle_filter_panel)

def _toggle_filter_panel(self, checked):
    """Toggle visibility of the filter panel.
    
    Args:
        checked: Whether the filter button is checked
    """
    if hasattr(self, "_filter_panel") and hasattr(self._filter_panel, "setVisible"):
        self._filter_panel.setVisible(checked)

def _on_filter_criteria_changed(self, criteria):
    """Handle changes to filter criteria.
    
    Args:
        criteria: New FilterCriteria object
    """
    if hasattr(self._proxy, "set_filter_criteria"):
        self._proxy.set_filter_criteria(criteria)