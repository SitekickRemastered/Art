package classes {
	
	import flash.display.MovieClip;
	import flash.events.Event;
	import flash.display.LoaderInfo;
	import flash.system.Security;
	import classes.control.GlobalControl;
	import classes.control.GameControl;
	import com.greensock.loading.SWFLoader;
	import com.greensock.loading.XMLLoader;
	import com.greensock.events.LoaderEvent;
	import classes.screens.LoadingScreen;
	
	public class Preloader extends MovieClip{

		private var _loadingScreen:LoadingScreen;
		private var _swf:MovieClip;
		private var _swfLoader:SWFLoader;
		private var _configLoader:XMLLoader;
		private var _mapLoader:XMLLoader;
		private var _loadCount:int;
		private var _totalCount:int;
		private var _totalPerc:Number;

		// Constructor
		public function Preloader() {
			Security.allowDomain("*");
			GlobalControl.init("Preloader");
			_loadingScreen = new LoadingScreen();
			_loadCount = 0;
			_totalCount = 1;
			_totalPerc = 0;
			
			var _paramObj:Object = LoaderInfo(this.root.loaderInfo).parameters;
			if (_paramObj["swfPath"] != undefined){
				if (_paramObj["swfPath"] != ""){
					GlobalControl._swfPath = _paramObj["swfPath"];
				}
			}
			
			if (_paramObj["configPath"] != undefined){
				if (_paramObj["configPath"] != ""){
					GlobalControl._configPath = _paramObj["configPath"];
				}
			}
			
			addChild (_loadingScreen);
			this.addEventListener(Event.ADDED_TO_STAGE, onAddedToStage);
		}
		
		// Private Methods
		private function onAddedToStage(e:Event):void{
			this.removeEventListener(Event.ADDED_TO_STAGE, onAddedToStage);
			_loadingScreen.animateIn(onLoadingAnimated);
		}
		
		private function onLoadingAnimated():void{
			_configLoader = new XMLLoader(GlobalControl._configPath, {onInit:onConfigLoaded});
			_configLoader.load();
		}
		
		private function onConfigLoaded(e:LoaderEvent):void{
			_totalCount += _configLoader.content.maps.level.length();
			_loadCount = 0;
			_mapLoader = new XMLLoader(_configLoader.content.maps.level[_loadCount], {onProgress:onMapLoadProgress, onComplete:onMapDataLoaded});
			_mapLoader.load();
		}
		
		private function onMapLoadProgress(e:LoaderEvent):void{
			if (e.target.progress < 1.0){
				_loadingScreen.update(_totalPerc + (e.target.progress)/_totalCount);
			}
		}
		
		private function onMapDataLoaded(e:LoaderEvent):void{
			GlobalControl._maps[_loadCount] = _mapLoader.content;
			_loadCount++;
			_totalPerc = _loadCount/_totalCount;
			if (_loadCount != _configLoader.content.maps.level.length()){
				_mapLoader = new XMLLoader(_configLoader.content.maps.level[_loadCount], {onProgress:onMapLoadProgress, onInit:onMapDataLoaded});
				_mapLoader.load();
			}else{
				_swfLoader = new SWFLoader(GlobalControl._swfPath, {onInit:onSwfLoaded, onProgress:onSwfLoadProgress});
				_swfLoader.load();
			}
		}
		
		private function onSwfLoadProgress(e:LoaderEvent):void{
			_loadingScreen.update(_totalPerc + (e.target.progress)/_totalCount);
		}
		
		private function onSwfLoaded(e:LoaderEvent):void{	
			_swf = MovieClip(_swfLoader.rawContent);
			addChild(_swf);
			_loadingScreen.animateOut(onLoadingScreenTransitionOut);
		}

		private function onLoadingScreenTransitionOut():void{
			removeChild(_loadingScreen);
			_loadingScreen.destroy();
			_swf.init();
		}
	}// Class
}// Package