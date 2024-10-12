package classes.events {
	
	import flash.events.Event;
	
	public class GameEvent extends Event{

		// Constants
		public static const BG_BUILT:String = "BG_BUILT";
		public static const HIT_WALL:String = "HIT_WALL";
		public static const GOT_KEY:String = "GOT_KEY";
		public static const SET_EMP:String = "SET_EMP";
		public static const CELL_UPDATE:String = "CELL_UPDATE";
		public static const LIFE_UP:String = "LIFE_UP";
		public static const LOSE_LIFE:String = "LOSE_LIFE";
		
		// Public Properties
		public var _data:Object;
		
		public function GameEvent(_t:String, _d:Object=null) {
			super(_t);
			_data = _d;
		}
		
		override public function clone():Event{
			return (new GameEvent(this.type, this._data));
		}

	}// Class
}// Package