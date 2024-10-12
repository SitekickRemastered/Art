package classes.events {
	
	import flash.events.Event;
	
	public class ScreenEvent extends Event{

		// Constants
		public static const PLAY_CLICK:String = "PLAY_CLICK";
		public static const INSTRUCTIONS_CLICK:String = "INSTRUCTIONS_CLICK";
		public static const SCORES_CLICK:String = "SCORES_CLICK";
		public static const GAME_OVER:String = "GAME_OVER";
		public static const INITIALIZED:String = "INITIALIZED";
		public static const ANIMATION_COMPLETE:String = "ANIMATION_COMPLETE";

		// Public Properties
		public var _data:Object;
		
		public function ScreenEvent(_t:String, _d:Object=null) {
			super(_t);
			_data = _d;
		}
		
		override public function clone():Event{
			return (new ScreenEvent(this.type, this._data));
		}

	}// Class
}// Package