package classes {
	
	import flash.display.MovieClip;
	import classes.control.ScreenControl;
	import classes.control.GlobalControl;
	import com.greensock.loading.XMLLoader;
	import com.greensock.events.LoaderEvent;
	
	public class Main extends MovieClip{
	
		// Private Properties
		private var _screenControl:ScreenControl;
		private var _configLoader:XMLLoader;
		private var _mapLoader:XMLLoader;
		private var _loadCount:int;
		private var _totalCount:int;
	
		// Constructor
		public function Main() {
			stop();
			_screenControl = new ScreenControl();		
			addChild (_screenControl);
			if (!GlobalControl._isInitialized){
				GlobalControl.init("Main");
				startLoads();
			}
		}
		
		// Public Methods
		public function init():void{
			trace ("screen control initialized");
			_screenControl.init();
		}
		
		// Private Methods
		private function startLoads():void{
			_totalCount = 1;
			_configLoader = new XMLLoader(GlobalControl._configPath, {onInit:onConfigLoaded});
			_configLoader.load();
		}
		
		private function onConfigLoaded(e:LoaderEvent):void{
			_totalCount += _configLoader.content.maps.level.length();
			_loadCount = 0;
			trace  ("loading map: "+_configLoader.content.maps.level[_loadCount]);
			_mapLoader = new XMLLoader(_configLoader.content.maps.level[_loadCount], {onProgress:onMapLoadProgress, onIOError:onMapLoadError, onFail:onMapLoadError, onInit:onMapDataLoaded});
			_mapLoader.load();
		}
		
		private function onMapLoadProgress(e:LoaderEvent):void{
			//trace((_loadCount/_totalCount) + ((1/_totalCount)*(e.target.bytesLoaded/e.target.bytesTotal)));
		}
		
		private function onMapDataLoaded(e:LoaderEvent):void{
			GlobalControl._maps[_loadCount] = _mapLoader.content;
			_loadCount++;
			if (_loadCount != _configLoader.content.maps.level.length()){
				_mapLoader = new XMLLoader(_configLoader.content.maps.level[_loadCount], {onProgress:onMapLoadProgress, onInit:onMapDataLoaded});
				_mapLoader.load();
			}else{
				init();
			}
		}
		
		private function onMapLoadError(e:LoaderEvent):void{
			trace ("error loading map: " +e.text);
		}

	}// Class
}// Package