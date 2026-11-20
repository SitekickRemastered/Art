#if UNITY_EDITOR
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.UI;

namespace Sitekick
{
	/// <summary>
	/// Builds Assets/Scenes/ChipGallery.unity: every chip in a 10 x 5 scrolling
	/// grid on the left, a Sitekick on the right, and a ChipGallery wiring the
	/// two together.
	/// </summary>
	public static class ChipGalleryBuilder
	{
		public const string ScenePath = "Assets/Scenes/ChipGallery.unity";
		public const string SitekickPrefabPath = "Assets/Sitekick/EditorSitekick.prefab";
		public const string ReportPath = "Logs/chip-gallery-check.txt";

		public const int Columns = 10;
		public const int Rows = 5;
		public const float Cell = 96f;
		public const float Gap = 4f;
		public const float Pad = 8f;

		// both the Sitekick and the chip effects are built from SWF art at the
		// same scale, so an effect at 1 is exactly the size it was in Flash
		public const float SitekickScale = 2.5f;
		public const float EffectScale = 1f;

		public static float ViewportWidth { get { return Columns * Cell + ( Columns - 1 ) * Gap + Pad * 2f; } }
		public static float ViewportHeight { get { return Rows * Cell + ( Rows - 1 ) * Gap + Pad * 2f; } }

		[MenuItem( "Sitekick/Build Chip Gallery Scene" )]
		public static void BuildFromMenu()
		{
			Build( true );
		}

		/// <summary>Batch entry point: <c>-executeMethod ChipGalleryBuilder.Run</c>.</summary>
		public static void Run()
		{
			Build( true );
		}

		public static void Build( bool save )
		{
			var scene = EditorSceneManager.NewScene( NewSceneSetup.EmptyScene, NewSceneMode.Single );

			var cameraGo = new GameObject( "Main Camera" );
			cameraGo.tag = "MainCamera";
			var camera = cameraGo.AddComponent<Camera>();
			camera.orthographic = true;
			camera.orthographicSize = 5.5f;
			camera.clearFlags = CameraClearFlags.SolidColor;
			camera.backgroundColor = new Color( 0.06f, 0.07f, 0.1f );
			cameraGo.transform.position = new Vector3( 0f, 0f, -10f );
			cameraGo.AddComponent<AudioListener>();

			var sitekick = PlaceSitekick();
			var content = BuildInterface();

			var galleryGo = new GameObject( "ChipGallery" );
			var gallery = galleryGo.AddComponent<ChipGallery>();
			var serialized = new SerializedObject( gallery );
			serialized.FindProperty( "content" ).objectReferenceValue = content;
			serialized.FindProperty( "sitekick" ).objectReferenceValue = sitekick.transform;
			serialized.FindProperty( "effectScale" ).floatValue = EffectScale;

			var entries = CollectEntries();
			var list = serialized.FindProperty( "entries" );
			list.arraySize = entries.Count;
			for ( int i = 0; i < entries.Count; i++ )
			{
				var element = list.GetArrayElementAtIndex( i );
				element.FindPropertyRelative( "id" ).intValue = entries[ i ].id;
				element.FindPropertyRelative( "icon" ).objectReferenceValue = entries[ i ].icon;
				element.FindPropertyRelative( "effect" ).objectReferenceValue = entries[ i ].effect;
				element.FindPropertyRelative( "layer" ).enumValueIndex = (int)entries[ i ].layer;
			}

			serialized.ApplyModifiedPropertiesWithoutUndo();

			Debug.Log( "chip gallery: " + entries.Count + " chips -> " + ScenePath );

			if ( save )
			{
				Directory.CreateDirectory( Path.GetDirectoryName( ScenePath ) );
				EditorSceneManager.SaveScene( scene, ScenePath );
			}
		}

		static GameObject PlaceSitekick()
		{
			var prefab = AssetDatabase.LoadAssetAtPath<GameObject>( SitekickPrefabPath );
			if ( prefab == null )
				throw new System.Exception( "missing " + SitekickPrefabPath );

			var instance = (GameObject)PrefabUtility.InstantiatePrefab( prefab );
			instance.name = "Sitekick";
			instance.transform.position = new Vector3( 5.2f, 0f, 0f );
			instance.transform.localScale = Vector3.one * SitekickScale;
			return instance;
		}

		static RectTransform BuildInterface()
		{
			var eventSystemGo = new GameObject( "EventSystem" );
			eventSystemGo.AddComponent<EventSystem>();
			eventSystemGo.AddComponent<StandaloneInputModule>();

			var canvasGo = new GameObject( "Canvas", typeof( Canvas ), typeof( CanvasScaler ), typeof( GraphicRaycaster ) );
			var canvas = canvasGo.GetComponent<Canvas>();
			canvas.renderMode = RenderMode.ScreenSpaceOverlay;

			var scaler = canvasGo.GetComponent<CanvasScaler>();
			scaler.uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
			scaler.referenceResolution = new Vector2( 1920f, 1080f );
			scaler.matchWidthOrHeight = 0.5f;

			var panelGo = new GameObject( "Chips", typeof( RectTransform ), typeof( Image ), typeof( ScrollRect ) );
			var panel = panelGo.GetComponent<RectTransform>();
			panel.SetParent( canvasGo.transform, false );
			panel.anchorMin = new Vector2( 0f, 0.5f );
			panel.anchorMax = new Vector2( 0f, 0.5f );
			panel.pivot = new Vector2( 0f, 0.5f );
			panel.anchoredPosition = new Vector2( 24f, 0f );
			panel.sizeDelta = new Vector2( ViewportWidth + 18f, ViewportHeight );

			var panelImage = panelGo.GetComponent<Image>();
			panelImage.color = new Color( 0.1f, 0.11f, 0.14f, 0.95f );

			var scrollRect = panelGo.GetComponent<ScrollRect>();
			scrollRect.horizontal = false;
			scrollRect.vertical = true;
			scrollRect.movementType = ScrollRect.MovementType.Clamped;
			scrollRect.scrollSensitivity = 40f;

			var viewportGo = new GameObject( "Viewport", typeof( RectTransform ), typeof( Image ), typeof( Mask ) );
			var viewport = viewportGo.GetComponent<RectTransform>();
			viewport.SetParent( panel, false );
			viewport.anchorMin = Vector2.zero;
			viewport.anchorMax = Vector2.one;
			viewport.pivot = new Vector2( 0f, 1f );
			viewport.offsetMin = new Vector2( 0f, 0f );
			viewport.offsetMax = new Vector2( -18f, 0f );

			viewportGo.GetComponent<Image>().color = new Color( 1f, 1f, 1f, 0.02f );
			viewportGo.GetComponent<Mask>().showMaskGraphic = false;

			var contentGo = new GameObject( "Content", typeof( RectTransform ), typeof( GridLayoutGroup ), typeof( ContentSizeFitter ) );
			var content = contentGo.GetComponent<RectTransform>();
			content.SetParent( viewport, false );
			content.anchorMin = new Vector2( 0f, 1f );
			content.anchorMax = new Vector2( 1f, 1f );
			content.pivot = new Vector2( 0.5f, 1f );
			content.anchoredPosition = Vector2.zero;
			content.sizeDelta = Vector2.zero;

			var grid = contentGo.GetComponent<GridLayoutGroup>();
			grid.constraint = GridLayoutGroup.Constraint.FixedColumnCount;
			grid.constraintCount = Columns;
			grid.cellSize = new Vector2( Cell, Cell );
			grid.spacing = new Vector2( Gap, Gap );
			grid.padding = new RectOffset( (int)Pad, (int)Pad, (int)Pad, (int)Pad );
			grid.childAlignment = TextAnchor.UpperLeft;

			contentGo.GetComponent<ContentSizeFitter>().verticalFit = ContentSizeFitter.FitMode.PreferredSize;

			var scrollbarGo = new GameObject( "Scrollbar", typeof( RectTransform ), typeof( Image ), typeof( Scrollbar ) );
			var scrollbar = scrollbarGo.GetComponent<RectTransform>();
			scrollbar.SetParent( panel, false );
			scrollbar.anchorMin = new Vector2( 1f, 0f );
			scrollbar.anchorMax = new Vector2( 1f, 1f );
			scrollbar.pivot = new Vector2( 1f, 0.5f );
			scrollbar.sizeDelta = new Vector2( 14f, 0f );
			scrollbar.anchoredPosition = Vector2.zero;

			var handleGo = new GameObject( "Handle", typeof( RectTransform ), typeof( Image ) );
			var handle = handleGo.GetComponent<RectTransform>();
			handle.SetParent( scrollbar, false );
			handle.anchorMin = Vector2.zero;
			handle.anchorMax = Vector2.one;
			handle.offsetMin = Vector2.zero;
			handle.offsetMax = Vector2.zero;

			var handleImage = handleGo.GetComponent<Image>();
			handleImage.color = new Color( 0.45f, 0.47f, 0.55f, 0.9f );

			var bar = scrollbarGo.GetComponent<Scrollbar>();
			bar.handleRect = handle;
			bar.targetGraphic = handleImage;
			bar.direction = Scrollbar.Direction.BottomToTop;

			scrollRect.viewport = viewport;
			scrollRect.content = content;
			scrollRect.verticalScrollbar = bar;
			scrollRect.verticalScrollbarVisibility = ScrollRect.ScrollbarVisibility.Permanent;

			return content;
		}

		public static List<ChipGallery.Entry> CollectEntries()
		{
			var entries = new List<ChipGallery.Entry>();

			foreach ( var guid in AssetDatabase.FindAssets( "t:ChipData", new[] { "Assets/Chips" } ) )
			{
				var path = AssetDatabase.GUIDToAssetPath( guid );
				var data = AssetDatabase.LoadAssetAtPath<ChipData>( path );
				if ( data == null )
					continue;

				var folder = Path.GetDirectoryName( path ).Replace( '\\', '/' );
				var name = "chip_" + data.id.ToString( "0000" );

				var entry = new ChipGallery.Entry
				{
					id = data.id,
					icon = AssetDatabase.LoadAssetAtPath<Sprite>( folder + "/Sprites/" + name + ".svg" ),
					effect = AssetDatabase.LoadAssetAtPath<GameObject>( folder + "/Chip_" + data.id.ToString( "0000" ) + "_Effect.prefab" ),
					layer = data.effectLayer
				};

				entries.Add( entry );
			}

			entries.Sort( ( a, b ) => a.id.CompareTo( b.id ) );
			return entries;
		}

		static Transform FindDeep( Transform parent, string name )
		{
			foreach ( var child in parent.GetComponentsInChildren<Transform>( true ) )
				if ( child.name == name )
					return child;

			return null;
		}

		static Bounds Bounds( GameObject go )
		{
			var renderers = go.GetComponentsInChildren<Renderer>( true );
			if ( renderers.Length == 0 )
				return new Bounds( go.transform.position, Vector3.zero );

			var bounds = renderers[ 0 ].bounds;
			for ( int i = 1; i < renderers.Length; i++ )
				bounds.Encapsulate( renderers[ i ].bounds );

			return bounds;
		}

		static string Size( Bounds b )
		{
			return b.size.x.ToString( "0.00" ) + " x " + b.size.y.ToString( "0.00" ) + " at " +
				b.center.x.ToString( "0.00" ) + "," + b.center.y.ToString( "0.00" );
		}

		/// <summary>
		/// Batch check: opens the scene, builds the grid, toggles a few chips and
		/// writes what happened to Logs/chip-gallery-check.txt.
		/// </summary>
		public static void Check()
		{
			var lines = new List<string>();
			bool failed = false;

			EditorSceneManager.OpenScene( ScenePath, OpenSceneMode.Single );

			var gallery = Object.FindFirstObjectByType<ChipGallery>();
			if ( gallery == null )
			{
				lines.Add( "FAIL no ChipGallery in scene" );
				File.WriteAllLines( ReportPath, lines );
				return;
			}

			lines.Add( "entries: " + gallery.EntryCount );
			if ( gallery.EntryCount != 1375 )
				failed = true;

			var layers = gallery.Sitekick != null
				? gallery.Sitekick.GetComponentsInChildren<EffectLayer>( true )
				: new EffectLayer[ 0 ];
			lines.Add( "effect layers: " + string.Join( ",", layers.Select( l => l.layer.ToString() ).ToArray() ) );
			if ( layers.Length != 4 )
				failed = true;

			// the Sitekick comes from sprite 214 frame 1 of sitekick.swf: its named
			// body pieces have to exist and the effect flags have to switch them
			var sitekick = gallery.Sitekick != null ? gallery.Sitekick.GetComponent<EditorSitekick>() : null;
			lines.Add( "sitekick prefab: " + ( sitekick != null ) );
			if ( sitekick == null )
			{
				failed = true;
			}
			else
			{
				var parts = new[] { "Antenna", "Body", "Eyes", "Stick", "Knob", "Washer", "Eye L", "Eye R" };
				foreach ( var part in parts )
				{
					var found = FindDeep( gallery.Sitekick, part );
					if ( found == null )
					{
						lines.Add( "missing part " + part );
						failed = true;
					}
				}

				lines.Add( "sitekick sprites: " + gallery.Sitekick.GetComponentsInChildren<SpriteRenderer>( true ).Length );

				sitekick.SetEffectFlags( ChipData.EffectFlags.HideAll );
				bool hidden = !FindDeep( gallery.Sitekick, "Body" ).gameObject.activeSelf &&
					!FindDeep( gallery.Sitekick, "Eyes" ).gameObject.activeSelf &&
					!FindDeep( gallery.Sitekick, "Antenna" ).gameObject.activeSelf;
				sitekick.SetEffectFlags( ChipData.EffectFlags.None );
				bool shown = FindDeep( gallery.Sitekick, "Body" ).gameObject.activeSelf &&
					FindDeep( gallery.Sitekick, "Eyes" ).gameObject.activeSelf &&
					FindDeep( gallery.Sitekick, "Antenna" ).gameObject.activeSelf;
				lines.Add( "effect flags: hide all " + hidden + ", show all " + shown );
				if ( !hidden || !shown )
					failed = true;
			}

			gallery.Build();
			lines.Add( "canvas: " + ( Object.FindFirstObjectByType<Canvas>() != null ) );

			var contentTransform = gallery.GetType()
				.GetField( "content", System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic );
			var rect = contentTransform != null ? contentTransform.GetValue( gallery ) as RectTransform : null;
			lines.Add( "item buttons: " + ( rect != null ? rect.childCount : -1 ) );
			if ( rect == null || rect.childCount != gallery.EntryCount )
				failed = true;

			var entries = gallery.Entries;
			foreach ( var layer in new[] { ChipData.EffectLayer.InFront, ChipData.EffectLayer.Background, ChipData.EffectLayer.Foreground } )
			{
				var entry = entries.FirstOrDefault( e => e.layer == layer && e.effect != null );
				if ( entry == null )
				{
					lines.Add( "no " + layer + " chip" );
					continue;
				}

				int before = gallery.ActiveCount;
				gallery.Toggle( entry.id );
				int after = gallery.ActiveCount;
				gallery.Toggle( entry.id );
				int off = gallery.ActiveCount;
				lines.Add( layer + " " + entry.id + ": " + before + " -> " + after + " -> " + off );
				if ( after != before + 1 || off != before )
					failed = true;
			}

			var infront = entries.FirstOrDefault( e => e.effect != null );
			int start = gallery.ActiveCount;
			gallery.Toggle( infront.id );
			var other = entries.FirstOrDefault( e => e.id != infront.id && e.effect != null );
			gallery.Toggle( other.id );
			lines.Add( "overlap: " + start + " -> " + gallery.ActiveCount );
			if ( gallery.ActiveCount != start + 2 )
				failed = true;

			gallery.ClearAll();
			lines.Add( "cleared: " + gallery.ActiveCount );
			if ( gallery.ActiveCount != 0 )
				failed = true;

			var camera = Object.FindFirstObjectByType<Camera>();
			if ( camera != null )
			{
				float height = camera.orthographicSize * 2f;
				lines.Add( "camera view: " + ( height * camera.aspect ).ToString( "0.00" ) + " x " + height.ToString( "0.00" ) );
				lines.Add( "sitekick x: " + gallery.Sitekick.position.x.ToString( "0.00" ) +
					" bounds: " + Size( Bounds( gallery.Sitekick.gameObject ) ) );
			}

			var sample = entries.FirstOrDefault( e => e.effect != null && e.layer == ChipData.EffectLayer.InFront );
		if ( sample != null )
		{
			gallery.Toggle( sample.id );
			var live = gallery.ActiveEffects.FirstOrDefault();
			if ( live != null )
			{
				var b = Bounds( live );
				lines.Add( "effect " + sample.id + " bounds: " + Size( b ) +
					" centre x " + b.center.x.ToString( "0.00" ) + " y " + b.center.y.ToString( "0.00" ) );
			}
			gallery.ClearAll();
		}

			lines.Add( failed ? "RESULT: FAIL" : "RESULT: OK" );
			File.WriteAllLines( ReportPath, lines );
			Debug.Log( string.Join( "\n", lines.ToArray() ) );
		}
	}
}
#endif
