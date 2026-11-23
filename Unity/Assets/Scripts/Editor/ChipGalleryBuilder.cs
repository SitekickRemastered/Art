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
			var content = BuildInterface( out var colorRow, out var picker );

			var galleryGo = new GameObject( "ChipGallery" );
			var gallery = galleryGo.AddComponent<ChipGallery>();
			var serialized = new SerializedObject( gallery );
			serialized.FindProperty( "content" ).objectReferenceValue = content;
			serialized.FindProperty( "sitekick" ).objectReferenceValue = sitekick.transform;
			serialized.FindProperty( "effectScale" ).floatValue = EffectScale;
			serialized.FindProperty( "iconMaterial" ).objectReferenceValue = IconMaterial();

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

			var panel = colorRow.GetComponent<ChipColorPanel>();
			var panelSerialized = new SerializedObject( panel );
			panelSerialized.FindProperty( "gallery" ).objectReferenceValue = gallery;
			panelSerialized.ApplyModifiedPropertiesWithoutUndo();

			var pickerSerialized = new SerializedObject( picker );
			pickerSerialized.FindProperty( "gallery" ).objectReferenceValue = gallery;
			pickerSerialized.FindProperty( "panel" ).objectReferenceValue = panel;
			pickerSerialized.ApplyModifiedPropertiesWithoutUndo();

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

		static RectTransform BuildInterface( out GameObject colorRow, out ColorPicker picker )
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

			var colorPanel = BuildColorRow( canvasGo.transform );
			colorRow = colorPanel.gameObject;
			picker = BuildColorPicker( canvasGo.transform, colorPanel );
			return content;
		}

		/// <summary>
		/// The colour field under the grid and the Apply button to its right: a hex
		/// value without the #, which <see cref="ChipColorPanel"/> reads when pressed.
		/// </summary>
		static ChipColorPanel BuildColorRow( Transform canvas )
		{
			var rowGo = new GameObject( "Color Row", typeof( RectTransform ) );
			var row = rowGo.GetComponent<RectTransform>();
			row.SetParent( canvas, false );
			row.anchorMin = new Vector2( 0f, 0.5f );
			row.anchorMax = new Vector2( 0f, 0.5f );
			row.pivot = new Vector2( 0f, 1f );
			row.anchoredPosition = new Vector2( 24f, -ViewportHeight * 0.5f - 12f );
			row.sizeDelta = new Vector2( ViewportWidth + 18f, 46f );

			var font = Resources.GetBuiltinResource<Font>( "LegacyRuntime.ttf" );

			var fieldGo = new GameObject( "Hex", typeof( RectTransform ), typeof( Image ), typeof( InputField ) );
			var fieldRect = fieldGo.GetComponent<RectTransform>();
			fieldRect.SetParent( row, false );
			fieldRect.anchorMin = new Vector2( 0f, 0f );
			fieldRect.anchorMax = new Vector2( 0f, 0f );
			fieldRect.pivot = new Vector2( 0f, 0f );
			fieldRect.anchoredPosition = Vector2.zero;
			fieldRect.sizeDelta = new Vector2( 300f, 46f );

			var fieldImage = fieldGo.GetComponent<Image>();
			fieldImage.color = new Color( 0.16f, 0.18f, 0.23f, 1f );

			var placeholder = MakeLabel( fieldRect, "Placeholder", "FFFFFF", font, new Color( 1f, 1f, 1f, 0.35f ) );
			var text = MakeLabel( fieldRect, "Text", "", font, Color.white );

			var field = fieldGo.GetComponent<InputField>();
			field.targetGraphic = fieldImage;
			field.textComponent = text;
			field.placeholder = placeholder;
			field.contentType = InputField.ContentType.Standard;
			field.lineType = InputField.LineType.SingleLine;
			field.characterLimit = 6;

			var buttonGo = new GameObject( "Apply", typeof( RectTransform ), typeof( Image ), typeof( Button ) );
			var buttonRect = buttonGo.GetComponent<RectTransform>();
			buttonRect.SetParent( row, false );
			buttonRect.anchorMin = new Vector2( 0f, 0f );
			buttonRect.anchorMax = new Vector2( 0f, 0f );
			buttonRect.pivot = new Vector2( 0f, 0f );
			buttonRect.anchoredPosition = new Vector2( 308f, 0f );
			buttonRect.sizeDelta = new Vector2( 96f, 46f );

			var buttonImage = buttonGo.GetComponent<Image>();
			buttonImage.color = new Color( 0.32f, 0.36f, 0.46f, 1f );

			var button = buttonGo.GetComponent<Button>();
			button.targetGraphic = buttonImage;

			var label = MakeLabel( buttonRect, "Label", "Apply", font, Color.white );
			label.alignment = TextAnchor.MiddleCenter;

			var panel = rowGo.AddComponent<ChipColorPanel>();
			var panelSerialized = new SerializedObject( panel );
			panelSerialized.FindProperty( "field" ).objectReferenceValue = field;
			panelSerialized.FindProperty( "apply" ).objectReferenceValue = button;
			panelSerialized.ApplyModifiedPropertiesWithoutUndo();

			return panel;
		}

		/// <summary>
		/// The live picker beside the hex row: an HSV square, a hue strip and the
		/// value it is publishing.  <see cref="ColorPicker"/> builds the gradient
		/// textures itself, so the scene only carries the rects.
		/// </summary>
		static ColorPicker BuildColorPicker( Transform canvas, ChipColorPanel panel )
		{
			var font = Resources.GetBuiltinResource<Font>( "LegacyRuntime.ttf" );

			var rootGo = new GameObject( "Color Picker", typeof( RectTransform ), typeof( Image ) );
			var root = rootGo.GetComponent<RectTransform>();
			root.SetParent( canvas, false );
			root.anchorMin = new Vector2( 0f, 0.5f );
			root.anchorMax = new Vector2( 0f, 0.5f );
			root.pivot = new Vector2( 0f, 1f );
			root.anchoredPosition = new Vector2( 24f + ViewportWidth + 18f + 16f, -ViewportHeight * 0.5f - 12f );
			root.sizeDelta = new Vector2( 206f, 238f );
			rootGo.GetComponent<Image>().color = new Color( 0.1f, 0.11f, 0.14f, 0.95f );

			var areaGo = new GameObject( "Area", typeof( RectTransform ), typeof( Image ) );
			var area = areaGo.GetComponent<RectTransform>();
			area.SetParent( root, false );
			area.anchorMin = new Vector2( 0f, 1f );
			area.anchorMax = new Vector2( 0f, 1f );
			area.pivot = new Vector2( 0f, 1f );
			area.anchoredPosition = new Vector2( 8f, -8f );
			area.sizeDelta = new Vector2( 190f, 160f );
			areaGo.GetComponent<Image>().color = Color.white;

			var hueGo = new GameObject( "Hue", typeof( RectTransform ), typeof( Image ) );
			var hue = hueGo.GetComponent<RectTransform>();
			hue.SetParent( root, false );
			hue.anchorMin = new Vector2( 0f, 1f );
			hue.anchorMax = new Vector2( 0f, 1f );
			hue.pivot = new Vector2( 0f, 1f );
			hue.anchoredPosition = new Vector2( 8f, -176f );
			hue.sizeDelta = new Vector2( 190f, 18f );
			hueGo.GetComponent<Image>().color = Color.white;

			var swatchGo = new GameObject( "Swatch", typeof( RectTransform ), typeof( Image ) );
			var swatch = swatchGo.GetComponent<RectTransform>();
			swatch.SetParent( root, false );
			swatch.anchorMin = new Vector2( 0f, 1f );
			swatch.anchorMax = new Vector2( 0f, 1f );
			swatch.pivot = new Vector2( 0f, 1f );
			swatch.anchoredPosition = new Vector2( 8f, -200f );
			swatch.sizeDelta = new Vector2( 30f, 30f );

			var readoutGo = new GameObject( "Readout", typeof( RectTransform ), typeof( Text ) );
			var readoutRect = readoutGo.GetComponent<RectTransform>();
			readoutRect.SetParent( root, false );
			readoutRect.anchorMin = new Vector2( 0f, 1f );
			readoutRect.anchorMax = new Vector2( 0f, 1f );
			readoutRect.pivot = new Vector2( 0f, 1f );
			readoutRect.anchoredPosition = new Vector2( 46f, -200f );
			readoutRect.sizeDelta = new Vector2( 152f, 30f );

			var readout = readoutGo.GetComponent<Text>();
			readout.font = font;
			readout.fontSize = 20;
			readout.text = "#FFFFFF";
			readout.color = Color.white;
			readout.alignment = TextAnchor.MiddleLeft;
			readout.horizontalOverflow = HorizontalWrapMode.Overflow;
			readout.supportRichText = false;

			var picker = rootGo.AddComponent<ColorPicker>();
			var serialized = new SerializedObject( picker );
			serialized.FindProperty( "panel" ).objectReferenceValue = panel;
			serialized.FindProperty( "area" ).objectReferenceValue = area;
			serialized.FindProperty( "hueBar" ).objectReferenceValue = hue;
			serialized.FindProperty( "swatch" ).objectReferenceValue = swatchGo.GetComponent<Image>();
			serialized.FindProperty( "readout" ).objectReferenceValue = readout;
			serialized.ApplyModifiedPropertiesWithoutUndo();

			var areaCursor = MakeCursor( area, "Area Cursor", 22f );
			var hueCursor = MakeCursor( hue, "Hue Cursor", 22f );

			serialized.Update();
			serialized.FindProperty( "areaCursor" ).objectReferenceValue = areaCursor;
			serialized.FindProperty( "hueCursor" ).objectReferenceValue = hueCursor;
			serialized.ApplyModifiedPropertiesWithoutUndo();

			return picker;
		}

		/// <summary>The ring that marks the picked point; the sprite comes from the picker.</summary>
		static RectTransform MakeCursor( RectTransform parent, string name, float size )
		{
			var go = new GameObject( name, typeof( RectTransform ), typeof( Image ) );
			var rect = go.GetComponent<RectTransform>();
			rect.SetParent( parent, false );
			rect.anchorMin = Vector2.zero;
			rect.anchorMax = Vector2.zero;
			rect.pivot = new Vector2( 0.5f, 0.5f );
			rect.anchoredPosition = Vector2.zero;
			rect.sizeDelta = new Vector2( size, size );

			var image = go.GetComponent<Image>();
			image.color = Color.white;
			image.raycastTarget = false;
			return rect;
		}

		static Text MakeLabel( RectTransform parent, string name, string value, Font font, Color color )
		{
			var go = new GameObject( name, typeof( RectTransform ), typeof( Text ) );
			var rect = go.GetComponent<RectTransform>();
			rect.SetParent( parent, false );
			rect.anchorMin = Vector2.zero;
			rect.anchorMax = Vector2.one;
			rect.offsetMin = new Vector2( 10f, 4f );
			rect.offsetMax = new Vector2( -10f, -4f );

			var label = go.GetComponent<Text>();
			label.font = font;
			label.fontSize = 22;
			label.text = value;
			label.color = color;
			label.alignment = TextAnchor.MiddleLeft;
			label.horizontalOverflow = HorizontalWrapMode.Overflow;
			label.supportRichText = false;
			return label;
		}

		/// <summary>
		/// Batch entry point: <c>-executeMethod ChipGalleryBuilder.AddColorRow</c>.
		/// Adds the colour row to the scene that is already on disk, without
		/// rebuilding the grid, so an existing scene keeps its ids.
		/// </summary>
		public static void AddColorRow()
		{
			EditorSceneManager.OpenScene( ScenePath, OpenSceneMode.Single );

			if ( Object.FindFirstObjectByType<ChipColorPanel>() != null )
			{
				Debug.Log( "chip gallery: colour row already present" );
				return;
			}

			var canvas = Object.FindFirstObjectByType<Canvas>();
			var gallery = Object.FindFirstObjectByType<ChipGallery>();
			if ( canvas == null || gallery == null )
				throw new System.Exception( "open " + ScenePath + " with a Canvas and a ChipGallery first" );

			var panel = BuildColorRow( canvas.transform );
			var serialized = new SerializedObject( panel );
			serialized.FindProperty( "gallery" ).objectReferenceValue = gallery;
			serialized.ApplyModifiedPropertiesWithoutUndo();

			EditorSceneManager.MarkSceneDirty( canvas.gameObject.scene );
			EditorSceneManager.SaveScene( canvas.gameObject.scene );
			Debug.Log( "chip gallery: colour row added" );
		}

		/// <summary>
		/// Batch entry point: <c>-executeMethod ChipGalleryBuilder.AddColorPicker</c>.
		/// Adds the live picker beside the colour row of the scene on disk, without
		/// rebuilding the grid.
		/// </summary>
		public static void AddColorPicker()
		{
			EditorSceneManager.OpenScene( ScenePath, OpenSceneMode.Single );

			if ( Object.FindFirstObjectByType<ColorPicker>() != null )
			{
				Debug.Log( "chip gallery: colour picker already present" );
				return;
			}

			var canvas = Object.FindFirstObjectByType<Canvas>();
			var gallery = Object.FindFirstObjectByType<ChipGallery>();
			var panel = Object.FindFirstObjectByType<ChipColorPanel>();
			if ( canvas == null || gallery == null || panel == null )
				throw new System.Exception( "open " + ScenePath + " with a Canvas, a ChipGallery and a colour row first" );

			var picker = BuildColorPicker( canvas.transform, panel );
			var serialized = new SerializedObject( picker );
			serialized.FindProperty( "gallery" ).objectReferenceValue = gallery;
			serialized.FindProperty( "panel" ).objectReferenceValue = panel;
			serialized.ApplyModifiedPropertiesWithoutUndo();

			EditorSceneManager.MarkSceneDirty( canvas.gameObject.scene );
			EditorSceneManager.SaveScene( canvas.gameObject.scene );
			Debug.Log( "chip gallery: colour picker added" );
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

				// the grid draws the chip's own vector sprite, at whatever the cell asks
				var icon = AssetDatabase.LoadAssetAtPath<Sprite>( folder + "/Sprites/" + name + ".svg" );

				var entry = new ChipGallery.Entry
				{
					id = data.id,
					icon = icon,
					effect = AssetDatabase.LoadAssetAtPath<GameObject>( folder + "/Chip_" + data.id.ToString( "0000" ) + "_Effect.prefab" ),
					layer = data.effectLayer
				};

				entries.Add( entry );
			}

			entries.Sort( ( a, b ) => a.id.CompareTo( b.id ) );
			return entries;
		}

		/// <summary>
		/// Shared material for the grid's vector icons: paints the colours baked into
		/// each cell's mesh and still honours the scroll view's clipping, which is what
		/// a baked PNG used to work around.
		/// </summary>
		public const string IconMaterialPath = "Assets/Materials/ChipIcon.mat";

		public static Material IconMaterial()
		{
			var existing = AssetDatabase.LoadAssetAtPath<Material>( IconMaterialPath );
			if ( existing != null )
				return existing;

			var shader = Shader.Find( "Sitekick/ChipIcon" );
			if ( shader == null )
			{
				Debug.LogError( "Sitekick/ChipIcon is missing" );
				return null;
			}

			Directory.CreateDirectory( Path.GetDirectoryName( IconMaterialPath ) );
			var material = new Material( shader ) { name = "ChipIcon" };
			AssetDatabase.CreateAsset( material, IconMaterialPath );
			return AssetDatabase.LoadAssetAtPath<Material>( IconMaterialPath );
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
		/// <summary>The renderers of `root` whose `_Color` block is set, for reports.</summary>
		static string Tints( Transform root )
		{
			if ( root == null )
				return "MISSING";

			var tints = new List<string>();
			foreach ( var renderer in root.GetComponentsInChildren<SpriteRenderer>( true ) )
			{
				var block = new MaterialPropertyBlock();
				renderer.GetPropertyBlock( block );
				var tint = block.GetColor( "_Color" );
				if ( tint.a > 0f && tint != Color.white )
					tints.Add( renderer.name + "=" + ColorUtility.ToHtmlStringRGB( tint ) );
			}

			return tints.Count > 0 ? string.Join( " ", tints.ToArray() ) : "white";
		}

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

			// the colour row: field, Apply and the Sitekick's paint, in edit mode
			var panel = Object.FindFirstObjectByType<ChipColorPanel>();
			lines.Add( "colour row: " + ( panel != null ) );
			if ( panel != null )
			{
				var panelData = new SerializedObject( panel );
				var field = panelData.FindProperty( "field" ).objectReferenceValue as InputField;
				var button = panelData.FindProperty( "apply" ).objectReferenceValue as Button;
				var wired = panelData.FindProperty( "gallery" ).objectReferenceValue as ChipGallery;
				failed |= field == null || button == null || wired == null;
				lines.Add( "  field: " + ( field != null ? field.name + " chars " + field.characterLimit : "MISSING" ) +
					", font " + ( field != null && field.textComponent != null && field.textComponent.font != null
						? field.textComponent.font.name : "MISSING" ) +
					", placeholder " + ( field != null && field.placeholder != null ? "yes" : "no" ) );
				lines.Add( "  apply: " + ( button != null ? button.name + " listeners " +
					button.onClick.GetPersistentEventCount() : "MISSING" ) );

				// the button's handler, called directly: Awake has not run in edit mode,
				// so onClick has no listener here (ChipPlayCheck covers the click)
				field.text = "ff3322";
				panel.ApplyField();
				lines.Add( "  typed ff3322 -> " + ColorUtility.ToHtmlStringRGB( wired.EffectColor ) );
				failed |= ColorUtility.ToHtmlStringRGB( wired.EffectColor ) != "FF3322";
				lines.Add( "  sitekick: " + Tints( wired.Sitekick ) );

				field.text = "";
				panel.ApplyField();
				lines.Add( "  cleared -> " + ColorUtility.ToHtmlStringRGB( wired.EffectColor ) );
				failed |= ColorUtility.ToHtmlStringRGB( wired.EffectColor ) != "FFFFFF";
				lines.Add( "  sitekick: " + Tints( wired.Sitekick ) );
			}

			lines.Add( failed ? "RESULT: FAIL" : "RESULT: OK" );
			File.WriteAllLines( ReportPath, lines );
			Debug.Log( string.Join( "\n", lines.ToArray() ) );
		}
	}
}
#endif
