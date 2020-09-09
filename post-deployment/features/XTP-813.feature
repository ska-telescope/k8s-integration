@VTS-226
Feature: Dish simulator confidence test via TM-Dish interface
	# The Dish Simulator behaviour is tested by invoking the commands of the Dish master TANGO
	# device and verifying that dishMode transitions are as per the documentation.
	# Scenario: Dish from dish_mode_a to dish_mode_b

	@XTP-813 @XTP-811
	Scenario Outline: Test dish-lmc-prototype dishMode change
		Given <dish_master> reports <start_mode> Dish mode
		When I command <dish_master> to <end_mode> Dish mode
		Then <dish_master> reports <end_mode> Dish mode
		And <dish_master> is in <end_state> state
		
		Examples:
		| dish_master             | start_mode | end_mode   | end_state |
		| mid_d0001/elt/master    | STANDBY-LP | STANDBY-FP | STANDBY   |
		| mid_d0001/elt/master    | STANDBY-FP | OPERATE    | ON        |
		| mid_d0001/elt/master    | OPERATE    | STANDBY-FP | STANDBY   |
		| mid_d0001/elt/master    | STANDBY-FP | STANDBY-LP | STANDBY   |