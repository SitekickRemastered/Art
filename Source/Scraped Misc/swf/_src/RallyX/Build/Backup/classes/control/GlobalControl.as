package classes.control {
	
	public class GlobalControl {
	
		// Constants
		//public static const BOARDPATH:String ="../scores/getGameHighScores.asp";
		public static const BOARDPATH:String ="http://dev-campnerf.corusinteractive.com/scores/getGameHighScores.asp";
		public static const GAME_ID:int = 510;
		
		// Public Properties
		public static var _configPath:String = "xml/config.xml";
		public static var _swfPath:String = "rallyx.swf";
		public static var _isInitialized:Boolean = false;	
		public static var _maps:Vector.<XML>;
		
		// Private Properties
		private static var _initializer:String = "";
		
		// Public Methods
		public static function init(_caller:String):void{
			trace("initialized: "+_caller);
			_isInitialized = true;
			_maps = new Vector.<XML>();
		}
		
		
		// Private Methods;
		
	}//Class
}//Package