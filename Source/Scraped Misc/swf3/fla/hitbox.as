package {
	import flash.external.ExternalInterface;
	public class hitbox {
		public function hitbox():void {
			trace("5 x 5 hitbox");
		}
		public function fire(arEvent:String, arAction:String, arExt:Boolean=true) {
			arEvent=arEvent.toLowerCase();
			arAction=arAction.toLowerCase();

			var lString:String="/flash/"+arEvent.toLowerCase()+"/"+arAction.toLowerCase();
			//trace("HitBox: " + lString);
			if (arExt) {
				try{
					ExternalInterface.call("_hbLink",lString);
				}catch (err:Error){
					trace("ERROR: No ExternalInterface available at this time");
				}
			}
		}
		//+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
		/**
		Logs an game event to our analytics provider
		
		Parameters:
			@activity = the activity to log (play, play again, instructions, etc)
			@isPlayActivity = whether or not this activity is a play event
		**/
		public function logGameEvent(activity:String, isPlayActivity:Boolean):void {
			//log for debugging
			trace("Calling Analytics.logGameEvent('"+ activity +"', "+ isPlayActivity.toString() +")");
			
			//call the javascript function
			ExternalInterface.call("Analytics.logGameEvent", activity, isPlayActivity);
		}
		
		/**
		Logs a navigation event with out analytics provider
		
		Parameters:
			@eventName = the name of the event to be used for tracking (could be a page name)
			
		Notes:
			Do not call this method from a game. All game activity should use logGameEvent 
			instead. This function is for use in other flash projects, like nav bars, 
			video players, etc.
		**/
		public function logClickEvent(eventName:String):void {
			//log for debugging
			trace("Calling Analytics.logClickEvent('"+ eventName +"')");
			
			//call the javascript function
			ExternalInterface.call("Analytics.logClickEvent", eventName);
		}
		//+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
		/**
		Logs a page view event from within flash
		
		Parameters:
			@hierarchy = the folder structure to report under (eg. /promos/[promoname]/)
			@pageName = the name of the page to report as (eg prizes, enter, about, etc)
		**/
		public function logPageView(hierarchy:String, pageName:String):void {
			//log for debugging
			trace("Calling Analytics.logPageView('"+ hierarchy +"', '"+ pageName +"')");
			
			//call the javascript function
			ExternalInterface.call("Analytics.logPageView", hierarchy, pageName);
		}
		//+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
	}
}

